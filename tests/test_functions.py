from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class FunctionSemanticTests(unittest.TestCase):
    def compile_source(self, source: str, add_main: bool = True) -> Compiler:
        if add_main:
            source = source.rstrip() + '\n\nfunc main() int32:\n    return 0\n'
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        compiler = Compiler()
        compiler.compile(path, executable=False)
        return compiler

    def test_function_scope_keeps_lexical_bindings_and_storage_manifest(self):
        compiler = self.compile_source(
            'base: const int32 = 3\n'
            'func suma(a: int32, b: int8) int32:\n'
            '    global base\n'
            '    total: int32 = a\n'
            '    if true:\n'
            '        nested: int32 = base\n'
            '    for index: uint32 ran (0, 3, 1):\n'
            '        loop_value: uint32 = index\n'
            '    return total\n'
        )

        function = compiler.storage.functions['suma']
        self.assertIsNotNone(function.scope)
        self.assertEqual(
            {'a', 'b', 'total'},
            set(function.scope.namespace),  # type: ignore[union-attr]
        )
        self.assertEqual(
            {'a', 'b', 'total', 'nested', 'loop_value'},
            set(function.local_variables),
        )
        self.assertIsNone(function.scope.resolve('nested'))  # type: ignore[union-attr]
        self.assertIs(function.scope.resolve('base'), compiler.storage.namespace['base'])

    def test_unique_requires_region_and_emits_noalias_for_arrays(self):
        source = (
            'func consume(left: unique int32[], left_len: Len_t, '
            'left_size: Size_t, left_region: Region_t, '
            'right: unique int32[], right_len: Len_t, '
            'right_size: Size_t, right_region: Region_t) void:\n'
            '    return\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int32:\n'
            + '    left: int32[2] = {1, 2}\n'
            + '    right: int32[2] = {3, 4}\n'
            + '    consume(left, right)\n'
            + '    return 0\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        ir_path = compiler.compile(path, executable=False)
        parameters = compiler.storage.functions['consume'].signature.parameters
        self.assertTrue(parameters[0].is_unique)
        self.assertTrue(parameters[3].is_region)
        self.assertIn('noalias', Path(ir_path).read_text(encoding='utf-8'))

    def test_unique_rejects_same_storage_and_missing_region(self):
        with self.assertRaisesRegex(CompilationError, 'debe declarar Region_t'):
            self.compile_source(
                'func bad(data: unique int32[], length: Len_t, size: Size_t) void:\n'
                '    return\n'
            )

        with self.assertRaisesRegex(CompilationError, 'solapa las regiones unique'):
            self.compile_source(
                'func bad(left: unique int32[], left_len: Len_t, '
                'left_size: Size_t, left_region: Region_t, '
                'right: unique int32[], right_len: Len_t, '
                'right_size: Size_t, right_region: Region_t) void:\n'
                '    return\n'
                '\n'
                'func caller() int32:\n'
                '    values: int32[2] = {1, 2}\n'
                '    bad(values, values)\n'
                '    return 0\n'
            )

    def test_unique_parameter_can_forward_its_region(self):
        compiler = self.compile_source(
            'func inner(data: unique int32[], length: Len_t, size: Size_t, '
            'region: Region_t) void:\n'
            '    return\n'
            '\n'
            'func outer(data: unique int32[], length: Len_t, size: Size_t, '
            'region: Region_t) void:\n'
            '    inner(data)\n'
            '    return\n'
        )
        self.assertTrue(
            compiler.storage.functions['outer'].signature.parameters[0].is_unique
        )

    def test_ordinary_array_aliasing_remains_legal(self):
        self.compile_source(
            'func consume(left: int32[], left_len: Len_t, left_size: Size_t, '
            'right: int32[], right_len: Len_t, right_size: Size_t) void:\n'
            '    return\n'
            '\n'
            'func caller() int32:\n'
            '    values: int32[2] = {1, 2}\n'
            '    consume(values, values)\n'
            '    return 0\n'
        )

    def test_unique_rejects_unknown_provenance_from_ordinary_parameter(self):
        with self.assertRaisesRegex(CompilationError, 'no puede demostrar la Region_t'):
            self.compile_source(
                'func inner(data: unique int32[], length: Len_t, size: Size_t, '
                'region: Region_t) void:\n'
                '    return\n'
                '\n'
                'func outer(data: int32[], length: Len_t, size: Size_t) void:\n'
                '    inner(data)\n'
                '    return\n'
            )

    def test_rejects_local_type_mismatch(self):
        with self.assertRaisesRegex(CompilationError, 'valor inicial de result'):
            self.compile_source(
                'func bad(value: int32) int32:\n'
                '    result: bool = value\n'
                '    return result\n'
            )

    def test_rejects_local_assignment_type_mismatch(self):
        with self.assertRaisesRegex(CompilationError, 'asignacion de result'):
            self.compile_source(
                'func bad(value: int32) int32:\n'
                '    result: int32 = value\n'
                '    result = true\n'
                '    return result\n'
            )

    def test_safe_char_array_cannot_write_reserved_nul(self):
        with self.assertRaisesRegex(CompilationError, 'terminador NUL'):
            self.compile_source(
                'func bad() int32:\n'
                '    buffer: char[5] = "Hola"\n'
                '    buffer[4] = "X"\n'
                '    return 0\n'
            )

        self.compile_source(
            '@unsafe\n'
            'func allowed() int32:\n'
            '    buffer: char[5] = "Hola"\n'
            '    buffer[4] = "X"\n'
            '    return 0\n'
        )

    def test_rejects_missing_return(self):
        with self.assertRaisesRegex(CompilationError, 'no tiene return'):
            self.compile_source(
                'func bad(value: int32) int32:\n'
                '    result: int32 = value\n'
                '    pass\n'
            )

    def test_return_only_inside_while_does_not_satisfy_function_return(self):
        with self.assertRaisesRegex(CompilationError, 'no tiene return'):
            self.compile_source(
                'func bad() int32:\n'
                '    while false:\n'
                '        return 1\n'
            )

    def test_if_with_else_satisfies_return_analysis(self):
        self.compile_source(
            'func choose(flag: bool) int32:\n'
            '    if flag:\n'
            '        return 1\n'
            '    else:\n'
            '        return 0\n'
        )

    def test_rejects_default_parameter(self):
        with self.assertRaisesRegex(CompilationError, 'valor por defecto'):
            self.compile_source(
                'func bad(value: int32 = 1) int32:\n'
                '    return value\n'
            )

    def test_rejects_unknown_function_decorators(self):
        for decorator in ('mystery', 'not_a_function_decorator'):
            with self.subTest(decorator=decorator):
                with self.assertRaisesRegex(
                    CompilationError,
                    rf'decorador @{decorator}.*funcion bad',
                ):
                    self.compile_source(
                        f'@{decorator}\n'
                        'func bad() int32:\n'
                        '    return 0\n'
                    )

    def test_rejects_duplicate_function_decorators(self):
        with self.assertRaisesRegex(
            CompilationError,
            r'decorador @unsafe esta repetido en bad',
        ):
            self.compile_source(
                '@unsafe\n'
                '@unsafe\n'
                'func bad() int32:\n'
                '    return 0\n'
            )

    def test_inline_is_recorded_in_function_symbol(self):
        compiler = self.compile_source(
            'inline func helper(value: int32) int32:\n'
            '    return value\n'
        )
        self.assertTrue(compiler.storage.functions['helper'].is_inline)

    def test_len_t_is_injected_for_a_concrete_array(self):
        source = (
            "clause Arch 'x86'\n"
            'func consume(buffer: char[], long: Len_t, size: Size_t) void:\n'
            '    return\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int32:\n'
            + '    buffer: char[16] = "Hola"\n'
            + '    consume(buffer)\n'
            + '    return 0\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        ir_path = compiler.compile(path, executable=False)
        metadata = compiler.storage.functions['consume'].signature.parameters
        self.assertEqual('usize', metadata[1].type_spec.name)
        self.assertEqual(32, metadata[1].type_spec.bit_width)
        module = Path(ir_path).read_text(encoding='utf-8')
        self.assertRegex(module, r'call void @"consume"\([^)]*i32 16, i32 1\)')

    def test_len_t_is_injected_for_a_static_chain(self):
        source = (
            'func consume(text: chain, length: Len_t) usize:\n'
            '    return length\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int32:\n'
            + '    message: chain = "Hola"\n'
            + '    result: usize = consume(message)\n'
            + '    return 0\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        ir_path = compiler.compile(path, executable=False)
        module = Path(ir_path).read_text(encoding='utf-8')
        self.assertRegex(module, r'call i64 @"consume"\([^)]*i64 5\)')

    def test_len_t_can_be_forwarded_for_a_chain_parameter(self):
        source = (
            'func consume(text: chain, length: Len_t) usize:\n'
            '    return length\n'
            'func relay(text: chain, length: Len_t) usize:\n'
            '    return consume(text)\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int32:\n'
            + '    message: chain = "Hola"\n'
            + '    result: usize = relay(message)\n'
            + '    return 0\n',
            encoding='utf-8',
        )
        Compiler().compile(path, executable=False)

    def test_len_t_rejects_an_unknown_chain_length(self):
        with self.assertRaisesRegex(CompilationError, 'chain.*Len_t'):
            self.compile_source(
                'func consume(text: chain, length: Len_t) usize:\n'
                '    return length\n'
                'func relay(text: chain) usize:\n'
                '    return consume(text)\n'
            )

    def test_safe_array_parameter_requires_len_t(self):
        with self.assertRaisesRegex(CompilationError, r'Len_t.*longitud'):
            self.compile_source(
                'func consume(buffer: char[]) void:\n'
                '    return\n'
            )

    def test_array_parameter_requires_size_t_after_len_t(self):
        with self.assertRaisesRegex(CompilationError, r'Size_t.*tamano'):
            self.compile_source(
                'func consume(buffer: char[], long: Len_t) void:\n'
                '    return\n'
            )

    def test_fixed_array_parameter_requires_both_metadata_types(self):
        with self.assertRaisesRegex(CompilationError, r'Len_t.*Size_t'):
            self.compile_source(
                'func consume(buffer: char[4]) void:\n'
                '    return\n'
            )

    def test_unsafe_array_parameter_also_requires_both_metadata_types(self):
        with self.assertRaisesRegex(CompilationError, r'Len_t.*Size_t'):
            self.compile_source(
                '@unsafe\n'
                'func consume(buffer: char[]) void:\n'
                '    return\n'
            )

    def test_array_metadata_must_be_ordered_len_then_size(self):
        with self.assertRaisesRegex(CompilationError, r'Len_t antes de Size_t'):
            self.compile_source(
                'func consume(buffer: char[], size: Size_t, long: Len_t) void:\n'
                '    return\n'
            )

    def test_matrix_parameters_require_all_dimensions(self):
        for matrix_type in ('int32[][]', 'int32[][3]', 'int32[2][]'):
            with self.subTest(matrix_type=matrix_type):
                with self.assertRaisesRegex(
                    CompilationError,
                    'debe declarar todas sus dimensiones',
                ):
                    self.compile_source(
                        f'func consume(data: {matrix_type}, rows: Len_t, '
                        'row_size: Size_t) void:\n'
                        '    return\n'
                    )

    def test_unsafe_cannot_bypass_fixed_matrix_shapes(self):
        for matrix_type in ('int32[][]', 'int32[][3]', 'int32[2][]'):
            with self.subTest(matrix_type=matrix_type):
                with self.assertRaisesRegex(
                    CompilationError,
                    'debe declarar todas sus dimensiones',
                ):
                    self.compile_source(
                        f'@unsafe\nfunc consume(data: {matrix_type}, '
                        'rows: Len_t, row_size: Size_t) void:\n'
                        '    return\n'
                    )

        with self.assertRaisesRegex(CompilationError, 'debe declarar todas sus dimensiones'):
            self.compile_source(
                '@unsafe\n'
                'func local_matrix() int32:\n'
                '    data: int32[2][] = {{1, 2}, {3, 4}}\n'
                '    return 0\n'
            )

    def test_matrices_are_limited_to_three_dimensions(self):
        with self.assertRaisesRegex(CompilationError, 'hasta tres dimensiones'):
            self.compile_source(
                'func consume(data: int32[2][3][4][5], depth: Len_t, '
                'block_size: Size_t) void:\n'
                '    return\n'
            )

    def test_fixed_matrix_parameter_is_a_reference_with_full_shape(self):
        source = (
            'func mutate(data: int32[2][3], rows: Len_t, row_size: Size_t) void:\n'
            '    data[0][0] = 99\n'
            '    return\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int32:\n'
            + '    matrix: int32[2][3] = {{1, 2, 3}, {4, 5, 6}}\n'
            + '    mutate(matrix)\n'
            + '    return matrix[0][0]\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        ir_path = compiler.compile(path, executable=False)
        module = Path(ir_path).read_text(encoding='utf-8')
        self.assertIn(
            'define void @"mutate"([2 x [3 x i32]]*',
            module,
        )
        self.assertRegex(
            module,
            r'call void @"mutate"\([^)]*i\d+ 2, i\d+ 12\)',
        )

    def test_fixed_one_dimensional_array_parameter_is_a_reference(self):
        source = (
            'func mutate(data: int32[3], length: Len_t, size: Size_t) void:\n'
            '    data[1] = 77\n'
            '    return\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int32:\n'
            + '    values: int32[3] = {1, 2, 3}\n'
            + '    mutate(values)\n'
            + '    return values[1]\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        ir_path = compiler.compile(path, executable=False)
        module = Path(ir_path).read_text(encoding='utf-8')
        self.assertIn('define void @"mutate"([3 x i32]*', module)

    def test_three_dimensional_matrix_size_is_the_outer_element_size(self):
        source = (
            'func inspect(data: int16[2][3][4], depth: Len_t, size: Size_t) usize:\n'
            '    return size\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int32:\n'
            + '    values: int16[2][3][4]\n'
            + '    result: usize = inspect(values)\n'
            + '    return 0\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        ir_path = compiler.compile(path, executable=False)
        module = Path(ir_path).read_text(encoding='utf-8')
        self.assertIn(
            'define i64 @"inspect"([2 x [3 x [4 x i16]]]*',
            module,
        )
        self.assertRegex(
            module,
            r'call i64 @"inspect"\([^)]*i\d+ 2, i\d+ 24\)',
        )

    def test_three_dimensional_shape_and_metadata_survive_forwarding(self):
        source = (
            'func sink(data: int32[2][3][4], depth: Len_t, block_size: Size_t) usize:\n'
            '    if depth != 2:\n'
            '        return 100\n'
            '    return block_size\n'
            'func forward(data: int32[2][3][4], depth: Len_t, block_size: Size_t) usize:\n'
            '    return sink(data)\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int32:\n'
            + '    values: int32[2][3][4]\n'
            + '    result: usize = forward(values)\n'
            + '    return 0\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        ir_path = compiler.compile(path, executable=False)
        module = Path(ir_path).read_text(encoding='utf-8')
        signature = '[2 x [3 x [4 x i32]]]*'
        self.assertIn(f'define i64 @"sink"({signature}', module)
        self.assertIn(f'define i64 @"forward"({signature}', module)
        self.assertRegex(
            module,
            r'call i64 @"sink"\([^)]*i64 %"[^\"]+", i64 %"[^\"]+"\)',
        )
        self.assertRegex(
            module,
            r'call i64 @"forward"\([^)]*i\d+ 2, i\d+ 48\)',
        )

    def test_matrix_argument_requires_the_exact_shape(self):
        with self.assertRaisesRegex(CompilationError, 'no coincide'):
            self.compile_source(
                'func consume(data: int32[2][3], rows: Len_t, '
                'row_size: Size_t) void:\n'
                '    return\n'
                'func bad() int32:\n'
                '    matrix: int32[2][4] = {{1, 2, 3, 4}, {5, 6, 7, 8}}\n'
                '    consume(matrix)\n'
                '    return 0\n'
            )

    def test_array_reference_rejects_literal_arguments(self):
        with self.assertRaisesRegex(CompilationError, 'almacenamiento propio'):
            self.compile_source(
                'func consume(data: int32[3], rows: Len_t, '
                'row_size: Size_t) void:\n'
                '    return\n'
                'func bad() int32:\n'
                '    consume({1, 2, 3})\n'
                '    return 0\n'
            )

    def test_matrix_constness_is_strict_at_call_boundaries(self):
        self.compile_source(
            'func read(data: const int32[2][3], rows: Len_t, '
            'row_size: Size_t) int32:\n'
            '    return data[0][0]\n'
            'func use() int32:\n'
            '    matrix: int32[2][3] = {{1, 2, 3}, {4, 5, 6}}\n'
            '    return read(matrix)\n'
        )

        with self.assertRaisesRegex(CompilationError, 'no coincide'):
            self.compile_source(
                'func write(data: int32[2][3], rows: Len_t, '
                'row_size: Size_t) void:\n'
                '    return\n'
                'func bad() int32:\n'
                '    matrix: const int32[2][3] = {{1, 2, 3}, {4, 5, 6}}\n'
                '    write(matrix)\n'
                '    return 0\n'
            )

    def test_matrix_literals_must_be_rectangular_and_complete(self):
        for initializer in (
            '{{1, 2}, {3, 4, 5}}',
            '{{1, 2, 3}, {4, 5}}',
            '{{1, 2}, {3}}',
        ):
            with self.subTest(initializer=initializer):
                with self.assertRaisesRegex(CompilationError, 'no coincide'):
                    self.compile_source(
                        'func bad() int32:\n'
                        f'    matrix: int32[2][3] = {initializer}\n'
                        '    return 0\n'
                    )

    def test_size_t_is_injected_for_a_scalar(self):
        source = (
            'func consume(value: int32, size: Size_t) usize:\n'
            '    return size\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int32:\n'
            + '    result: usize = consume(10)\n'
            + '    return 0\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        ir_path = compiler.compile(path, executable=False)
        module = Path(ir_path).read_text(encoding='utf-8')
        self.assertRegex(module, r'call i64 @"consume"\(i32 10, i64 4\)')

    def test_size_t_is_injected_as_array_element_bytes(self):
        source = (
            'func consume(values: int32[], long: Len_t, size: Size_t) usize:\n'
            '    return size\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int32:\n'
            + '    values: int32[3] = {1, 2, 3}\n'
            + '    result: usize = consume(values)\n'
            + '    return 0\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        ir_path = compiler.compile(path, executable=False)
        module = Path(ir_path).read_text(encoding='utf-8')
        self.assertRegex(module, r'call i64 @"consume"\([^)]*i64 4\)')

    def test_expansion_parameters_cannot_be_const_or_pointers(self):
        with self.assertRaisesRegex(CompilationError, 'Len_t ya es inmutable'):
            self.compile_source(
                'func bad(values: char[], long: const Len_t) void:\n'
                '    return\n'
            )

        with self.assertRaisesRegex(CompilationError, 'Len_t.*punteros'):
            self.compile_source(
                'func bad(values: char[], long *: Len_t) void:\n'
                '    return\n'
            )

    def test_len_t_rejects_a_scalar_source(self):
        with self.assertRaisesRegex(CompilationError, r'char\[\]|Len_t'):
            self.compile_source(
                'func consume(buffer: char[], long: Len_t, size: Size_t) void:\n'
                '    return\n'
                'func bad() int32:\n'
                '    letter: char = "A"\n'
                '    consume(letter)\n'
                '    return 0\n'
            )

    def test_array_metadata_can_be_forwarded_between_strict_parameters(self):
        self.compile_source(
            'func consume(buffer: char[], long: Len_t, size: Size_t) void:\n'
            '    return\n'
            'func relay(buffer: char[], long: Len_t, size: Size_t) void:\n'
            '    consume(buffer)\n'
            '    return\n'
        )

    def test_void_function_accepts_empty_return(self):
        self.compile_source(
            'func done(value: int32) void:\n'
            '    copy: int32 = value\n'
            '    return\n'
        )

    def test_void_function_requires_an_empty_return(self):
        with self.assertRaisesRegex(CompilationError, 'void.*return'):
            self.compile_source(
                'func done() void:\n'
                '    pass\n'
            )

    def test_void_call_cannot_be_used_as_a_value(self):
        with self.assertRaisesRegex(CompilationError, 'solo puede llamarse'):
            self.compile_source(
                'func done() void:\n'
                '    return\n'
                'func bad() int32:\n'
                '    return done()\n'
            )

    def test_void_is_not_a_value_parameter_or_local(self):
        with self.assertRaisesRegex(CompilationError, 'no puede usar void'):
            self.compile_source(
                'func bad(value: void) int32:\n'
                '    return 0\n'
            )

    def test_numeric_for_requires_uint_iterator_and_nonzero_step(self):
        for iterator_type in ('bool', 'int32', 'int64', 'usize', 'byte', 'uint'):
            with self.subTest(iterator_type=iterator_type):
                with self.assertRaisesRegex(
                    CompilationError,
                    'exactamente un tipo uint8/uint16/uint32/uint64',
                ):
                    self.compile_source(
                        f'func bad() int32:\n'
                        f'    for i: {iterator_type} ran (1, 3, 1):\n'
                        f'        pass\n'
                        f'    return 0\n'
                    )

    def test_numeric_for_accepts_only_fixed_unsigned_widths(self):
        self.compile_source(
            'func good() int32:\n'
            '    for a: uint8 ran (0, 2, 1):\n'
            '        pass\n'
            '    for b: uint16 ran (0, 2, 1):\n'
            '        pass\n'
            '    for c: uint32 ran (0, 2, 1):\n'
            '        pass\n'
            '    for d: uint64 ran (0, 2, 1):\n'
            '        pass\n'
            '    return 0\n'
        )

    def test_nested_for_rejects_repeated_iterator(self):
        with self.assertRaisesRegex(
            CompilationError,
            'La variable i ya fue declarada en el scope',
        ):
            self.compile_source(
                'func bad() int32:\n'
                '    for i: uint32 ran (0, 2, 1):\n'
                '        for i: uint32 ran (0, 2, 1):\n'
                '            pass\n'
                '    return 0\n'
            )

    def test_nested_for_allows_distinct_iterators(self):
        self.compile_source(
            'func good() int32:\n'
            '    for outer: uint32 ran (0, 2, 1):\n'
            '        for inner: uint32 ran (0, 2, 1):\n'
            '            pass\n'
            '    return 0\n'
        )

    def test_numeric_for_rejects_literal_zero_step(self):
        with self.assertRaisesRegex(CompilationError, 'step.*cero'):
            self.compile_source(
                'func bad() int32:\n'
                '    for i: uint32 ran (1, 3, 0):\n'
                '        pass\n'
                '    return 0\n'
            )

    def test_numeric_for_rejects_negative_step_for_uint(self):
        with self.assertRaisesRegex(CompilationError, 'no coincide con uint32'):
            self.compile_source(
                'func bad() int32:\n'
                '    for i: uint32 ran (3, 0, -1):\n'
                '        pass\n'
                '    return 0\n'
            )

    def test_numeric_for_iterator_is_local_and_read_only(self):
        with self.assertRaisesRegex(CompilationError, 'iterador.*solo lectura'):
            self.compile_source(
                'func bad() int32:\n'
                '    for i: uint32 ran (1, 3, 1):\n'
                '        i = 2\n'
                '        pass\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'no existe'):
            self.compile_source(
                'func bad() int32:\n'
                '    for i: uint32 ran (1, 3, 1):\n'
                '        pass\n'
                '    return i\n'
            )

    def test_numeric_for_rejects_non_uint_step_expression(self):
        with self.assertRaisesRegex(CompilationError, 'no coincide con uint32'):
            self.compile_source(
                'func bad(step: int32) int32:\n'
                '    for i: uint32 ran (1, 3, step):\n'
                '        pass\n'
                '    return 0\n'
            )

    def test_numeric_for_uses_the_target_signed_ceiling(self):
        with self.assertRaisesRegex(
            CompilationError,
            'limite maximo de iteracion del target',
        ):
            self.compile_source(
                "clause Arch 'x86'\n"
                'func bad() int32:\n'
                '    for i: uint64 ran (0, 2147483648, 1):\n'
                '        pass\n'
                '    return 0\n'
            )

    def test_if_conditions_require_bool_scalars(self):
        with self.assertRaisesRegex(
            CompilationError,
            'condicion de if.*debe ser bool',
        ):
            self.compile_source(
                'func bad() int32:\n'
                '    value: int32 = 1\n'
                '    if value:\n'
                '        return 1\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(
            CompilationError,
            'condicion de if.*debe ser bool',
        ):
            self.compile_source(
                'func bad() int32:\n'
                '    value: double = 1.0\n'
                '    if value:\n'
                '        return 1\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(
            CompilationError,
            'operandos logicos.*deben ser bool',
        ):
            self.compile_source(
                'func bad() int32:\n'
                '    if 1 && true:\n'
                '        return 1\n'
                '    return 0\n'
            )

    def test_logical_not_is_a_keyword_and_word_and_or_are_not(self):
        self.compile_source(
            'func check(flag: bool) bool:\n'
            '    if not not flag:\n'
            '        return true\n'
            '    return false\n'
        )

        with self.assertRaises(SystemExit):
            self.compile_source(
                'func invalid(flag: bool) bool:\n'
                '    if flag and true:\n'
                '        return true\n'
                '    return false\n'
            )

        with self.assertRaises(SystemExit):
            self.compile_source(
                'func invalid(flag: bool) bool:\n'
                '    if flag or true:\n'
                '        return true\n'
                '    return false\n'
            )

    def test_nested_locals_are_not_visible_outside_their_block(self):
        with self.assertRaisesRegex(CompilationError, 'variable global no existe'):
            self.compile_source(
                'func invalid() int32:\n'
                '    if true:\n'
                '        hidden: int32 = 7\n'
                '    return hidden\n'
            )

    def test_nested_scalar_locals_require_an_initializer(self):
        with self.assertRaisesRegex(CompilationError, 'debe tener un inicializador'):
            self.compile_source(
                'func invalid() int32:\n'
                '    if true:\n'
                '        hidden: int32\n'
                '        return 0\n'
                '    return 0\n'
            )

    def test_while_requires_a_bool_condition(self):
        with self.assertRaisesRegex(
            CompilationError,
            'condicion de while.*debe ser bool',
        ):
            self.compile_source(
                'func bad() int32:\n'
                '    while 1:\n'
                '        break\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(
            CompilationError,
            'condicion de while.*debe ser bool',
        ):
            self.compile_source(
                'func bad(value: int32) int32:\n'
                '    while value:\n'
                '        break\n'
                '    return 0\n'
            )

        self.compile_source(
            'func good(value: int32) int32:\n'
            '    while value != 0:\n'
            '        return 1\n'
            '    return 0\n'
        )

    def test_class_methods_are_deferred(self):
        compiler = self.compile_source(
            'class Box:\n'
            '    func init(value: int32) void:\n'
            '        return\n'
        )
        self.assertEqual({'main'}, set(compiler.storage.functions))

    def test_class_method_does_not_satisfy_global_main(self):
        with self.assertRaisesRegex(CompilationError, 'funcion global main'):
            self.compile_source(
                'class Box:\n'
                '    func main() void:\n'
                '        pass\n',
                add_main=False,
            )

    def test_rejects_break_and_continue_outside_loops(self):
        with self.assertRaisesRegex(CompilationError, 'solo puede usarse dentro de un bucle'):
            self.compile_source(
                'func main() int32:\n'
                '    break\n'
                '    return 0\n'
            )


if __name__ == '__main__':
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class FunctionSemanticTests(unittest.TestCase):
    def compile_source(self, source: str, add_main: bool = True) -> Compiler:
        if add_main:
            source = source.rstrip() + '\n\nfunc main() int:\n    return 0\n'
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        compiler = Compiler()
        compiler.compile(path, executable=False)
        return compiler

    def test_function_scope_contains_parameters_and_nested_locals(self):
        compiler = self.compile_source(
            'base: const int = 3\n'
            'func suma(a: int, b: Bint<5>) int:\n'
            '    total: int = a\n'
            '    if true:\n'
            '        nested: int = base\n'
            '    for index: int ran (0, 3, 1):\n'
            '        loop_value: int = index\n'
            '    return total\n'
        )

        function = compiler.storage.functions['suma']
        self.assertIsNotNone(function.scope)
        self.assertEqual(
            {'a', 'b', 'total', 'nested', 'index', 'loop_value'},
            set(function.scope.namespace),  # type: ignore[union-attr]
        )
        self.assertIs(function.scope.resolve('base'), compiler.storage.namespace['base'])

    def test_rejects_local_type_mismatch(self):
        with self.assertRaisesRegex(CompilationError, 'valor inicial de result'):
            self.compile_source(
                'func bad(value: int) int:\n'
                '    result: bool = value\n'
                '    return result\n'
            )

    def test_rejects_local_assignment_type_mismatch(self):
        with self.assertRaisesRegex(CompilationError, 'asignacion de result'):
            self.compile_source(
                'func bad(value: int) int:\n'
                '    result: int = value\n'
                '    result = true\n'
                '    return result\n'
            )

    def test_safe_char_array_cannot_write_reserved_nul(self):
        with self.assertRaisesRegex(CompilationError, 'terminador NUL'):
            self.compile_source(
                'func bad() int:\n'
                '    buffer: char[5] = "Hola"\n'
                '    buffer[4] = "X"\n'
                '    return 0\n'
            )

        self.compile_source(
            '@unsafe\n'
            'func allowed() int:\n'
            '    buffer: char[5] = "Hola"\n'
            '    buffer[4] = "X"\n'
            '    return 0\n'
        )

    def test_rejects_missing_return(self):
        with self.assertRaisesRegex(CompilationError, 'no tiene return'):
            self.compile_source(
                'func bad(value: int) int:\n'
                '    result: int = value\n'
                '    pass\n'
            )

    def test_rejects_default_parameter(self):
        with self.assertRaisesRegex(CompilationError, 'valor por defecto'):
            self.compile_source(
                'func bad(value: int = 1) int:\n'
                '    return value\n'
            )

    def test_len_t_is_injected_for_a_concrete_array(self):
        source = (
            'func consume(buffer: char[], long: Len_t, size: Size_t) void:\n'
            '    return\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int:\n'
            + '    buffer: char[5] = "Hola"\n'
            + '    consume(buffer)\n'
            + '    return 0\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        ir_path = compiler.compile(path, executable=False)
        module = Path(ir_path).read_text(encoding='utf-8')
        self.assertRegex(module, r'call void @"consume"\([^)]*i64 5\)')

    def test_len_t_is_injected_for_a_static_chain(self):
        source = (
            'func consume(text: chain, length: Len_t) uint64:\n'
            '    return length\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int:\n'
            + '    message: chain = "Hola"\n'
            + '    result: uint64 = consume(message)\n'
            + '    return 0\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        ir_path = compiler.compile(path, executable=False)
        module = Path(ir_path).read_text(encoding='utf-8')
        self.assertRegex(module, r'call i64 @"consume"\([^)]*i64 5\)')

    def test_len_t_can_be_forwarded_for_a_chain_parameter(self):
        source = (
            'func consume(text: chain, length: Len_t) uint64:\n'
            '    return length\n'
            'func relay(text: chain, length: Len_t) uint64:\n'
            '    return consume(text)\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int:\n'
            + '    message: chain = "Hola"\n'
            + '    result: uint64 = relay(message)\n'
            + '    return 0\n',
            encoding='utf-8',
        )
        Compiler().compile(path, executable=False)

    def test_len_t_rejects_an_unknown_chain_length(self):
        with self.assertRaisesRegex(CompilationError, 'chain.*Len_t'):
            self.compile_source(
                'func consume(text: chain, length: Len_t) uint64:\n'
                '    return length\n'
                'func relay(text: chain) uint64:\n'
                '    return consume(text)\n'
            )

    def test_safe_array_parameter_requires_len_t(self):
        with self.assertRaisesRegex(CompilationError, r'Len_t.*longitud'):
            self.compile_source(
                'func consume(buffer: char[]) void:\n'
                '    return\n'
            )

    def test_size_t_is_injected_for_a_scalar(self):
        source = (
            'func consume(value: int32, size: Size_t) uint64:\n'
            '    return size\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int:\n'
            + '    result: uint64 = consume(10)\n'
            + '    return 0\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        ir_path = compiler.compile(path, executable=False)
        module = Path(ir_path).read_text(encoding='utf-8')
        self.assertRegex(module, r'call i64 @"consume"\(i32 10, i64 4\)')

    def test_size_t_is_injected_as_total_array_bytes(self):
        source = (
            'func consume(values: int32[], long: Len_t, size: Size_t) uint64:\n'
            '    return size\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            source
            + '\nfunc main() int:\n'
            + '    values: int32[3] = {1, 2, 3}\n'
            + '    result: uint64 = consume(values)\n'
            + '    return 0\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        ir_path = compiler.compile(path, executable=False)
        module = Path(ir_path).read_text(encoding='utf-8')
        self.assertRegex(module, r'call i64 @"consume"\([^)]*i64 12\)')

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
                'func consume(buffer: char[], long: Len_t) void:\n'
                '    return\n'
                'func bad() int:\n'
                '    letter: char = "A"\n'
                '    consume(letter)\n'
                '    return 0\n'
            )

    def test_len_t_rejects_an_array_without_a_compile_time_length(self):
        with self.assertRaisesRegex(CompilationError, 'Len_t.*longitud'):
            self.compile_source(
                'func consume(buffer: char[], long: Len_t) void:\n'
                '    return\n'
                'func relay(buffer: char[]) void:\n'
                '    consume(buffer)\n'
                '    return\n'
            )

    def test_void_function_accepts_empty_return(self):
        self.compile_source(
            'func done(value: int) void:\n'
            '    copy: int = value\n'
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
                'func bad() int:\n'
                '    return done()\n'
            )

    def test_void_is_not_a_value_parameter_or_local(self):
        with self.assertRaisesRegex(CompilationError, 'no puede usar void'):
            self.compile_source(
                'func bad(value: void) int:\n'
                '    return 0\n'
            )

    def test_numeric_for_requires_integer_iterator_and_nonzero_step(self):
        with self.assertRaisesRegex(CompilationError, 'tipo entero escalar'):
            self.compile_source(
                'func bad() int:\n'
                '    for i: bool ran (1, 3, 1):\n'
                '        pass\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'step.*cero'):
            self.compile_source(
                'func bad() int:\n'
                '    for i: int32 ran (1, 3, 0):\n'
                '        pass\n'
                '    return 0\n'
            )

    def test_conditions_require_bool_or_integer_scalars(self):
        with self.assertRaisesRegex(CompilationError, 'debe ser bool o entero escalar'):
            self.compile_source(
                'func bad() int:\n'
                '    value: double = 1.0\n'
                '    if value:\n'
                '        return 1\n'
                '    return 0\n'
            )

    def test_class_methods_are_deferred(self):
        compiler = self.compile_source(
            'class Box:\n'
            '    func init(value: int) void:\n'
            '        pass\n'
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
                'func main() int:\n'
                '    break\n'
                '    return 0\n'
            )


if __name__ == '__main__':
    unittest.main()

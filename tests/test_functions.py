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

    def test_void_function_accepts_empty_return(self):
        self.compile_source(
            'func done(value: int) void:\n'
            '    copy: int = value\n'
            '    return\n'
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

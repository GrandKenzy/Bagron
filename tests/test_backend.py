from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class GlobalBackendTests(unittest.TestCase):
    def compile_source(self, source: str, add_main: bool = True) -> str:
        if add_main:
            source = source.rstrip() + '\n\nfunc main() bool:\n    return true\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(source, encoding='utf-8')
            output = Compiler().compile(path)
            return Path(output).read_text(encoding='utf-8')

    def test_emits_literals_bint_arrays_and_const_references(self):
        module = self.compile_source(
            'base: const int = 10\n'
            'copy: int = base\n'
            'small: Bint<5> = 15\n'
            'mask: uBint<5> = 31\n'
            'values: uBint<5>[] = [1, 2, 3]\n'
        )

        self.assertIn('global i32 10', module)
        self.assertIn('global i5 15', module)
        self.assertIn('global [3 x i5]', module)

    def test_emits_bool_main_as_llvm_entrypoint(self):
        module = self.compile_source('value: int = 1\n')

        self.assertIn('define i1 @"main"()', module)
        self.assertIn('ret i1 true', module)

    def test_rejects_mutable_global_reference(self):
        with self.assertRaisesRegex(CompilationError, 'global mutable base'):
            self.compile_source('base: int = 10\ncopy: int = base\n')

    def test_rejects_mutable_reference_inside_array(self):
        with self.assertRaisesRegex(CompilationError, 'global mutable base'):
            self.compile_source(
                'base: int = 10\n'
                'values: int[] = [base]\n'
            )

    def test_rejects_invalid_arch(self):
        with self.assertRaisesRegex(CompilationError, 'valor invalido'):
            self.compile_source("clause Arch 'invalid'\nvalue: int = 1\n")

    def test_accepts_explicit_llvm_triple(self):
        from llvmlite import binding as llvm

        triple = llvm.get_default_triple()
        module = self.compile_source(
            f"clause Arch '{triple}'\n"
            'value: int = 1\n'
        )
        self.assertIn(f'target triple = "{triple}"', module)

    def test_requires_global_main(self):
        with self.assertRaisesRegex(CompilationError, 'funcion global main'):
            self.compile_source('value: int = 1\n', add_main=False)

    def test_main_requires_bool_without_parameters(self):
        with self.assertRaisesRegex(CompilationError, 'debe retornar bool'):
            self.compile_source(
                'func main() int:\n'
                '    return 0\n',
                add_main=False,
            )

        with self.assertRaisesRegex(CompilationError, 'no puede recibir parametros'):
            self.compile_source(
                'func main(value: int) bool:\n'
                '    return true\n',
                add_main=False,
            )


if __name__ == '__main__':
    unittest.main()

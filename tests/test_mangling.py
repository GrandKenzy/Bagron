from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from core.compiler import Compiler
from core.compiler.mangling import MANGLE_VERSION
from core.library import pack_library, read_library


class ManglingTests(unittest.TestCase):
    @staticmethod
    def _package(root: Path, name: str, value: int) -> Path:
        source = root / name / 'source'
        source.mkdir(parents=True)
        (source / 'api.bg').write_text(
            f'public value: const int32 = {value}\n'
            'public func convert() int32:\n'
            '    return value\n'
            'public struct Thing:\n'
            '    value: int32\n',
            encoding='utf-8',
        )
        package = root / 'libs' / f'{name}.lib'
        package.parent.mkdir(exist_ok=True)
        pack_library(source, package, name=name, version='1.0.0')
        return package

    def test_two_lib1_packages_with_same_api_do_not_collide(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._package(root, 'A', 11)
            self._package(root, 'B', 22)
            main = root / 'main.bg'
            main.write_text(
                'library "A.lib" as A\n'
                'library "B.lib" as B\n'
                'func main() int32:\n'
                '    return A.convert() + B.convert()\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=False)
            module = Path(artifacts).read_text(encoding='utf-8')
            names = {
                line.split('@', 1)[1].split()[0].strip('"')
                for line in module.splitlines()
                if line.lstrip().startswith('define i32')
                and '__bg_' in line
            }
            self.assertEqual(2, len(names), module)
            self.assertEqual(2, module.count('call i32 @__bg_'))

    def test_globals_and_nominal_types_receive_distinct_llvm_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._package(root, 'A', 1)
            self._package(root, 'B', 2)
            a = read_library(root / 'libs' / 'A.lib')
            b = read_library(root / 'libs' / 'B.lib')
            a_symbols = {
                item['name']: item['llvm']
                for item in a.symbols['exports']
                if item['kind'] in {'variable', 'type'}
            }
            b_symbols = {
                item['name']: item['llvm']
                for item in b.symbols['exports']
                if item['kind'] in {'variable', 'type'}
            }
            self.assertTrue(a_symbols)
            self.assertTrue(b_symbols)
            self.assertTrue(set(a_symbols.values()).isdisjoint(b_symbols.values()))

    def test_mangling_is_deterministic_and_versioned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self._package(root, 'Stable', 7)
            first_symbols = read_library(first).symbols
            second = root / 'libs' / 'Stable-copy.lib'
            pack_library(root / 'Stable' / 'source', second, name='Stable', version='1.0.0')
            second_symbols = read_library(second).symbols
            self.assertEqual(MANGLE_VERSION, first_symbols['mangling'])
            self.assertEqual(first_symbols, second_symbols)

    def test_main_and_extern_keep_their_abi_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / 'main.bg'
            main.write_text(
                "clause System 'windows'\n"
                'extern windows "kernel32":\n'
                '    GetCurrentProcessId() uint32\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )
            module = Path(Compiler().compile(main, executable=False)).read_text(
                encoding='utf-8'
            )
            self.assertRegex(module, r'declare i32 @"?GetCurrentProcessId"?\(')
            self.assertRegex(module, r'define i32 @"?main"?\(')
            self.assertNotRegex(module, r'declare i32 @"?__bg_[^\s"]*GetCurrentProcessId')


if __name__ == '__main__':
    unittest.main()

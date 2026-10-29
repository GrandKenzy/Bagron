from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import subprocess

from core.compiler import CompilationError, Compiler


class ModuleAndNativeIncludeTests(unittest.TestCase):
    def test_import_loads_bagron_module_before_main(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'math.bg').write_text(
                'func doble(value: int32) int32:\n'
                '    return value + value\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import math\n'
                'func main() int32:\n'
                '    return doble(3)\n',
                encoding='utf-8',
            )

            compiler = Compiler()
            output = compiler.compile(main, executable=False)
            module = Path(output).read_text(encoding='utf-8')

        self.assertIn('define i32 @"doble"', module)
        self.assertIn('call i32 @"doble"(i32 3)', module)
        self.assertEqual(2, len(compiler.storage.loaded_modules))

    def test_import_reports_missing_module(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'import missing\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'No se encontro el modulo'):
                Compiler().compile(main, executable=False)

    def test_import_alias_calls_qualified_function(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'math.bg').write_text(
                'func doble(value: int32) int32:\n'
                '    return value + value\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import math as m\n'
                'func main() int32:\n'
                '    return m.doble(3)\n',
                encoding='utf-8',
            )

            module_path = Compiler().compile(main, executable=False)
            module = Path(module_path).read_text(encoding='utf-8')

        self.assertIn('call i32 @"doble"(i32 3)', module)

    def test_import_selective_alias_calls_function(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'math.bg').write_text(
                'func doble(value: int32) int32:\n'
                '    return value + value\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import { doble as twice } from math\n'
                'func main() int32:\n'
                '    return twice(3)\n',
                encoding='utf-8',
            )

            module_path = Compiler().compile(main, executable=False)
            module = Path(module_path).read_text(encoding='utf-8')

        self.assertIn('call i32 @"doble"(i32 3)', module)

    def test_include_resolves_header_and_link(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'include "windows" link "kernel32"\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            compiler = Compiler()
            artifacts = compiler.compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual('windows.h', compiler.storage.native_includes[0].header)
        self.assertEqual('kernel32', compiler.storage.native_includes[0].library)
        self.assertEqual(['kernel32'], compiler.storage.native_links)

    def test_import_reports_cycles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'a.bg').write_text(
                'import b\n'
                'func doble(value: int32) int32:\n'
                '    return value + value\n',
                encoding='utf-8',
            )
            (root / 'b.bg').write_text(
                'import a\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import a\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'Ciclo de importacion'):
                Compiler().compile(main, executable=False)

    def test_include_rejects_unknown_header(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'include "does_not_exist" link "kernel32"\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'header nativo'):
                Compiler().compile(main, executable=False)


if __name__ == '__main__':
    unittest.main()

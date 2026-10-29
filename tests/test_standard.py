from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class StandardLibraryTests(unittest.TestCase):
    def test_print_writes_chain_using_windows_abi(self):
        project_source = Path(__file__).resolve().parents[1] / 'standard.bg'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(project_source, root / 'standard.bg')
            main = root / '_main.bg'
            main.write_text(
                'import standard\n'
                '@unsafe\n'
                'func main() int:\n'
                '    message: chain = "Hola"\n'
                '    source: const char[6] = "Adios"\n'
                '    converted: chain = source\n'
                '    buffer: char[5] = "Hola"\n'
                '    print(message)\n'
                '    print(" / DOLLAR")\n'
                '    print(converted)\n'
                '    printa(buffer)\n'
                '    return 0\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            module = artifacts.ir.read_text(encoding='utf-8')
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual(b'Hola / DOLLARAdiosHola\x00', result.stdout)
        self.assertEqual(2, module.count('call i32 @"WriteFile"'))
        self.assertRegex(module, r'call void @"printa"\([^)]*i64 5, i64 5\)')

    def test_printa_rejects_scalar_char(self):
        project_source = Path(__file__).resolve().parents[1] / 'standard.bg'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(project_source, root / 'standard.bg')
            main = root / '_main.bg'
            main.write_text(
                'import standard\n'
                '@unsafe\n'
                'func main() int:\n'
                '    letter: char = "A"\n'
                '    printa(letter)\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'printa'):
                Compiler().compile(main, executable=False)

    def test_serialize_int_appends_decimal_text(self):
        project_source = Path(__file__).resolve().parents[1] / 'standard.bg'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(project_source, root / 'standard.bg')
            main = root / '_main.bg'
            main.write_text(
                'import standard\n'
                '@unsafe\n'
                'func main() int:\n'
                '    positive: char[50] = "Mi edad es: "\n'
                '    negative: char[50] = "Negativo: "\n'
                '    zero: char[50] = "Cero: "\n'
                '    positioned: char[50] = "Posicion: 999"\n'
                '    serialize_int(positive, 20)\n'
                '    serialize_int(negative, -20)\n'
                '    serialize_int(zero, 0)\n'
                '    serialize_int_at(positioned, 10, 123)\n'
                '    printa(positive)\n'
                '    printa(negative)\n'
                '    printa(zero)\n'
                '    printa(positioned)\n'
                '    return 0\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)
        expected = b''.join(
            value.ljust(50, b'\x00')
            for value in (
                b'Mi edad es: 20',
                b'Negativo: -20',
                b'Cero: 0',
                b'Posicion: 123',
            )
        )
        self.assertEqual(expected, result.stdout)


if __name__ == '__main__':
    unittest.main()

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler
from core.frontend.objects import DefinedIntegerSymbol
from core.library import pack_library


class DefinedIntegerBoundaryTests(unittest.TestCase):
    """Stress source-defined integer widths, signedness, and package ABI."""

    def _compile(self, source: str, *, executable: bool = False):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        compiler = Compiler()
        artifacts = compiler.compile(path, executable=executable)
        return compiler, artifacts

    def test_small_and_large_widths_emit_their_exact_llvm_integer_types(self):
        compiler, artifacts = self._compile(
            '#defint 1, I1\n'
            '#defuint 2, U2\n'
            '#defint 4, I4\n'
            '#defuint 128, U128\n'
            'signed_one: I1 = 0\n'
            'unsigned_two: U2 = 3\n'
            'signed_four: I4 = -7\n'
            'unsigned_wide: U128 = 123\n'
            'func main() int32:\n'
            '    return 0\n',
            executable=False,
        )

        module = Path(artifacts).read_text(encoding='utf-8')
        self.assertIn('global i1 ', module)
        self.assertIn('global i2 ', module)
        self.assertIn('global i4 ', module)
        self.assertIn('global i128 ', module)
        for name, width, signed in (
            ('I1', 1, True),
            ('U2', 2, False),
            ('I4', 4, True),
            ('U128', 128, False),
        ):
            with self.subTest(name=name):
                symbol = compiler.storage.types[name]
                self.assertIsInstance(symbol, DefinedIntegerSymbol)
                self.assertEqual(width, symbol.bit_width)
                self.assertEqual(signed, symbol.signed)

    def test_signed_and_unsigned_arithmetic_use_distinct_integer_operations(self):
        _, artifacts = self._compile(
            '#defint 4, I4\n'
            '#defuint 4, U4\n'
            'func signed_div(value: I4) I4:\n'
            '    return value / 3\n'
            'func unsigned_div(value: U4) U4:\n'
            '    return value / 3\n'
            'func main() int32:\n'
            '    return 0\n',
            executable=False,
        )

        module = Path(artifacts).read_text(encoding='utf-8')
        self.assertIn('sdiv i4', module)
        self.assertIn('udiv i4', module)

    def test_integer_literals_cannot_exceed_defined_width_ranges(self):
        invalid_sources = (
            '#defint 4, I4\n'
            'value: I4 = 8\n',
            '#defuint 4, U4\n'
            'value: U4 = 16\n',
        )

        for prefix in invalid_sources:
            with self.subTest(prefix=prefix):
                with self.assertRaisesRegex(CompilationError, 'no coincide con'):
                    self._compile(
                        prefix
                        + 'func main() int32:\n'
                        + '    return 0\n'
                    )

    def test_duplicate_and_reserved_defined_integer_names_are_rejected(self):
        invalid_sources = (
            '#defint 8, int8\n',
            '#defint 8, Bint\n',
            '#defint 8, Same\n'
            '#defuint 8, Same\n',
        )

        for prefix in invalid_sources:
            with self.subTest(prefix=prefix):
                with self.assertRaises(CompilationError):
                    self._compile(
                        prefix
                        + 'func main() int32:\n'
                        + '    return 0\n'
                    )

    def test_signed_and_unsigned_defined_integers_round_trip_through_library_abi(self):
        with tempfile.TemporaryDirectory(prefix='bagron-defined-integer-library-') as directory:
            root = Path(directory)
            source = root / 'source'
            (source / 'modules').mkdir(parents=True)
            (source / 'modules' / 'numbers.bg').write_text(
                '#defint 4, SmallSigned\n'
                '#defuint 128, WideUnsigned\n'
                'public func signed_identity(value: SmallSigned) SmallSigned:\n'
                '    return value\n'
                'public func unsigned_identity(value: WideUnsigned) WideUnsigned:\n'
                '    return value\n',
                encoding='utf-8',
            )
            package = root / 'libs' / 'Numbers.lib'
            package.parent.mkdir()
            pack_library(source, package, name='Numbers', version='1.0.0')

            main = root / 'main.bg'
            main.write_text(
                'library "Numbers.lib" as Numbers\n'
                'func main() int32:\n'
                '    signed: Numbers.SmallSigned = -3\n'
                '    wide: Numbers.WideUnsigned = 7\n'
                '    signed_result: Numbers.SmallSigned = Numbers.signed_identity(signed)\n'
                '    wide_result: Numbers.WideUnsigned = Numbers.unsigned_identity(wide)\n'
                '    return 0\n',
                encoding='utf-8',
            )
            artifacts = Compiler().compile(main)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr.decode())
            self.assertTrue(package.is_file())

        self.assertFalse(root.exists())


if __name__ == '__main__':
    unittest.main()

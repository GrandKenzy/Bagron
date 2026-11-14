from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

from core.compiler import CompilationError, Compiler
from core.frontend.objects import AggregateSymbol, DefinedIntegerSymbol


class FieldsAndDefinedIntegerTests(unittest.TestCase):
    def compile_source(self, source: str, *, executable: bool = False) -> Compiler:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(source, encoding='utf-8')
            compiler = Compiler()
            compiler.compile(path, executable=executable)
            return compiler

    def test_fields_accepts_positional_limbs_and_signed_bit(self):
        compiler = self.compile_source(
            '@signed\n'
            'fields int128:\n'
            '    lo: Bint(64)\n'
            '    hi: Bint(64)\n'
            'func main() int32:\n'
            '    edad: int32 = 10\n'
            '    enterogrande: int128 = {edad, 100}\n'
            '    return 0\n'
        )
        symbol = compiler.storage.types['int128']
        self.assertIsInstance(symbol, AggregateSymbol)
        self.assertEqual('fields', symbol.kind)
        self.assertTrue(symbol.signed_fields)
        self.assertEqual([64, 64], [field.type_spec.bit_width for field in symbol.fields])

    def test_defined_integer_is_scalar_and_public(self):
        compiler = self.compile_source(
            '#defint 128, int128\n'
            'value: int128 = 100\n'
            'func add(value: int128) int128:\n'
            '    return value + 1\n'
            'func main() int32:\n'
            '    value2: int128 = add(value)\n'
            '    return 0\n'
        )
        symbol = compiler.storage.types['int128']
        self.assertIsInstance(symbol, DefinedIntegerSymbol)
        self.assertEqual(128, symbol.bit_width)
        self.assertTrue(symbol.signed)

    def test_defined_unsigned_integer_supports_full_scalar_use(self):
        compiler = self.compile_source(
            '#defuint 128, uint128\n'
            'func increment(value: uint128) uint128:\n'
            '    return value + 1\n'
            'func main() int32:\n'
            '    value: uint128 = 100\n'
            '    result: uint128 = increment(value)\n'
            '    return 0\n'
        )
        symbol = compiler.storage.types['uint128']
        self.assertIsInstance(symbol, DefinedIntegerSymbol)
        self.assertFalse(symbol.signed)

    def test_defined_integer_widths_and_fields_collisions_are_rejected(self):
        for directive in ('#defint 0, Zero\n', '#defuint 0, Zero\n'):
            with self.subTest(directive=directive):
                with self.assertRaisesRegex(CompilationError, 'mayor que cero'):
                    self.compile_source(
                        directive
                        + 'func main() int32:\n'
                        + '    return 0\n'
                    )

        with self.assertRaises(CompilationError):
            self.compile_source(
                '#defint 128, Shared\n'
                'fields Shared:\n'
                '    limb: Bint(64)\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaises(CompilationError):
            self.compile_source(
                'fields Shared:\n'
                '    limb: Bint(64)\n'
                '#defuint 128, Shared\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_fields_literal_can_be_passed_to_a_function(self):
        self.compile_source(
            'fields Pair:\n'
            '    lo: Bint(1)\n'
            '    hi: Bint(33)\n'
            'func consume(pair: Pair) int32:\n'
            '    return 0\n'
            'func main() int32:\n'
            '    consume({1, 100})\n'
            '    return 0\n',
            executable=True,
        )

    def test_defined_integer_is_exported_by_an_imported_module(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'modules').mkdir()
            (root / 'modules' / 'numbers.bg').write_text(
                '#defint 128, Word\n'
                'public func identity(value: Word) Word:\n'
                '    return value\n',
                encoding='utf-8',
            )
            main = root / 'main.bg'
            main.write_text(
                'import numbers\n'
                'func main() int32:\n'
                '    value: numbers.Word = 7\n'
                '    result: numbers.Word = numbers.identity(value)\n'
                '    return 0\n',
                encoding='utf-8',
            )
            artifacts = Compiler().compile(main)
            self.assertTrue(Path(artifacts.executable).is_file())

    def test_old_spellings_are_rejected(self):
        for source in (
            'flags X uint8:\n    bit: uBint<1> = 1\n',
            'value: uBint<8> = 1\n',
            'value: Bint<8> = 1\n',
        ):
            with self.assertRaises((CompilationError, SystemExit)):
                self.compile_source(source)


if __name__ == '__main__':
    unittest.main()

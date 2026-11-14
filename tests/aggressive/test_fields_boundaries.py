from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler
from core.library import pack_library


class FieldsBoundaryTests(unittest.TestCase):
    """Stress structural fields layout, positional literals, and diagnostics."""

    def _compile(self, source: str, *, executable: bool = True):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        return Compiler().compile(path, executable=executable)

    def _run(self, source: str) -> int:
        artifacts = self._compile(source)
        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual('', result.stderr.decode(), result.stderr.decode())
        return result.returncode

    def test_round_trip_all_limb_widths_and_mutations(self):
        self.assertEqual(
            0,
            self._run(
                'fields Bits:\n'
                '    one: Bint(1)\n'
                '    two: Bint(2)\n'
                '    twelve: Bint(12)\n'
                '    thirty_three: Bint(33)\n'
                '    sixty_four: Bint(64)\n'
                'func main() int32:\n'
                '    bits: Bits = {1, 3, 4095, 100, 123}\n'
                '    if bits.one != 1:\n'
                '        return 1\n'
                '    if bits.two != 3:\n'
                '        return 2\n'
                '    if bits.twelve != 4095:\n'
                '        return 3\n'
                '    if bits.thirty_three != 100:\n'
                '        return 4\n'
                '    if bits.sixty_four != 123:\n'
                '        return 5\n'
                '    bits.one = 0\n'
                '    bits.two = 2\n'
                '    bits.twelve = 12\n'
                '    if bits.one != 0:\n'
                '        return 6\n'
                '    if bits.two != 2:\n'
                '        return 7\n'
                '    if bits.twelve != 12:\n'
                '        return 8\n'
                '    return 0\n'
            ),
        )

    def test_signed_fields_use_one_hidden_sign_member(self):
        ir_path = self._compile(
            '@signed\n'
            'fields SignedBits:\n'
            '    low: Bint(64)\n'
            '    high: Bint(64)\n'
            'value: SignedBits = {1, 2}\n'
            'func main() int32:\n'
            '    return 0\n',
            executable=False,
        )
        module = Path(ir_path).read_text(encoding='utf-8')
        self.assertRegex(module, r'= type \{ \{ i64, i64, i1 \} \}')

    def test_positional_literals_require_exact_arity(self):
        for literal, message in (('{1}', 'exactamente 2'), ('{1, 2, 3}', 'exactamente 2')):
            with self.subTest(literal=literal):
                with self.assertRaisesRegex(CompilationError, message):
                    self._compile(
                        'fields Pair:\n'
                        '    low: Bint(64)\n'
                        '    high: Bint(64)\n'
                        'func main() int32:\n'
                        f'    pair: Pair = {literal}\n'
                        '    return 0\n',
                        executable=False,
                    )

    def test_signed_decorator_is_the_only_fields_decorator(self):
        with self.assertRaises(CompilationError):
            self._compile(
                '@packed\n'
                'fields Invalid:\n'
                '    value: Bint(1)\n'
                'func main() int32:\n'
                '    return 0\n',
                executable=False,
            )

    def test_fields_reject_initializers_and_non_bint_members(self):
        for declaration in (
            '    value: Bint(8) = 0\n',
            '    value: uint8\n',
        ):
            with self.subTest(declaration=declaration):
                with self.assertRaises(CompilationError):
                    self._compile(
                        'fields Invalid:\n'
                        + declaration
                        + 'func main() int32:\n'
                        + '    return 0\n',
                        executable=False,
                    )

    def test_defined_integer_round_trips_through_library_abi(self):
        with tempfile.TemporaryDirectory(prefix='bagron-fields-library-') as directory:
            root = Path(directory)
            source = root / 'source'
            (source / 'modules').mkdir(parents=True)
            (source / 'modules' / 'numbers.bg').write_text(
                '#defuint 128, Word\n'
                'public func bump(value: Word) Word:\n'
                '    return value + 1\n',
                encoding='utf-8',
            )
            package = root / 'libs' / 'Numbers.lib'
            package.parent.mkdir()
            pack_library(source, package, name='Numbers', version='1.0.0')

            main = root / 'main.bg'
            main.write_text(
                'library "Numbers.lib" as Numbers\n'
                'func main() int32:\n'
                '    value: Numbers.Word = 7\n'
                '    result: Numbers.Word = Numbers.bump(value)\n'
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

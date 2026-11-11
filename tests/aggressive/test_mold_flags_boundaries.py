from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class MoldFlagsBoundaryTests(unittest.TestCase):
    """Stress overlay storage and packed bitfield invariants."""

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

    def test_flags_round_trip_all_widths_and_mutations(self):
        self.assertEqual(
            0,
            self._run(
                'flags Bits uint8:\n'
                '    low: uBint<1> = 1\n'
                '    middle_bits: uBint<3> = 5\n'
                '    high: uBint<4> = 10\n'
                'func main() int32:\n'
                '    bits: Bits\n'
                '    if bits.low != 1:\n'
                '        return 1\n'
                '    if bits.middle_bits != 5:\n'
                '        return 2\n'
                '    if bits.high != 10:\n'
                '        return 3\n'
                '    bits.low = 0\n'
                '    bits.middle_bits = 3\n'
                '    bits.high = 15\n'
                '    if bits.low != 0:\n'
                '        return 4\n'
                '    if bits.middle_bits != 3:\n'
                '        return 5\n'
                '    if bits.high != 15:\n'
                '        return 6\n'
                '    return 0\n'
            ),
        )

    def test_flags_signed_bitfield_preserves_sign_extension(self):
        self.assertEqual(
            0,
            self._run(
                'flags SignedBits uint8:\n'
                '    delta: Bint<3> = -1\n'
                '    enabled: bool = true\n'
                '    reserved: uBint<4> = 0\n'
                'func main() int32:\n'
                '    bits: SignedBits\n'
                '    if bits.delta != -1:\n'
                '        return 1\n'
                '    if not bits.enabled:\n'
                '        return 2\n'
                '    bits.delta = -4\n'
                '    if bits.delta != -4:\n'
                '        return 3\n'
                '    return 0\n'
            ),
        )

    def test_order_msb_changes_offsets_without_changing_field_values(self):
        self.assertEqual(
            0,
            self._run(
                '@order_msb\n'
                'flags NetworkBits uint8:\n'
                '    version: uBint<3> = 5\n'
                '    kind: uBint<5> = 17\n'
                'func main() int32:\n'
                '    bits: NetworkBits\n'
                '    if bits.version != 5:\n'
                '        return 1\n'
                '    if bits.kind != 17:\n'
                '        return 2\n'
                '    bits.version = 2\n'
                '    bits.kind = 31\n'
                '    if bits.version != 2:\n'
                '        return 3\n'
                '    if bits.kind != 31:\n'
                '        return 4\n'
                '    return 0\n'
            ),
        )

    def test_mold_overlay_supports_nested_access_and_literal_zeroing(self):
        self.assertEqual(
            0,
            self._run(
                'mold View:\n'
                '    whole: uint32\n'
                '    bytes: byte[4]\n'
                'struct Holder:\n'
                '    view: View\n'
                '    marker: uint8\n'
                'func main() int32:\n'
                '    holder: Holder = Holder{\n'
                '        .view = View{ .whole = 0 },\n'
                '        .marker = 9,\n'
                '    }\n'
                '    holder.view.bytes[0] = 7\n'
                '    if holder.view.bytes[0] != 7:\n'
                '        return 1\n'
                '    if holder.view.bytes[3] != 0:\n'
                '        return 2\n'
                '    if holder.marker != 9:\n'
                '        return 3\n'
                '    return 0\n'
            ),
        )

    def test_flags_reject_incomplete_or_overlapping_bit_layouts(self):
        for source, message in (
            (
                'flags MissingBits uint8:\n'
                '    value: uBint<7> = 0\n',
                'ocupan 7 bits',
            ),
            (
                'flags TooManyBits uint8:\n'
                '    first: uBint<8> = 0\n'
                '    second: uBint<1> = 0\n',
                'ocupan 9 bits',
            ),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(CompilationError, message):
                    self._compile(
                        source
                        + 'func main() int32:\n'
                        + '    return 0\n',
                        executable=False,
                    )

    def test_flags_reject_bad_bases_widths_and_field_initializers(self):
        cases = (
            ('flags SignedBase int8:\n    value: uBint<8> = 0\n', 'uint8/16/32/64'),
            ('flags ByteBase byte:\n    value: uBint<8> = 0\n', 'uint8/16/32/64'),
            ('flags OneBitSigned uint8:\n    value: Bint<1> = 0\n', 'al menos 2 bits'),
            ('flags ZeroBit uint8:\n    value: uBint<0> = 0\n', 'mayor que cero'),
            ('flags BadValue uint8:\n    value: uBint<8> = 256\n', 'no coincide con uBint<8>'),
            ('flags BadBool uint8:\n    value: bool = 1\n', 'literal booleano'),
        )
        for declaration, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(CompilationError, message):
                    self._compile(
                        declaration
                        + 'func main() int32:\n'
                        + '    return 0\n',
                        executable=False,
                    )

    def test_mold_requires_one_active_literal_view(self):
        with self.assertRaisesRegex(CompilationError, 'exactamente un campo'):
            self._compile(
                'mold View:\n'
                '    word: uint32\n'
                '    bytes: byte[4]\n'
                'func main() int32:\n'
                '    view: View = View{ .word = 1, .bytes = {1, 2, 3, 4} }\n'
                '    return 0\n',
                executable=False,
            )

    def test_aggregate_decorators_are_rejected_on_the_wrong_kind(self):
        with self.assertRaisesRegex(CompilationError, 'order_msb'):
            self._compile(
                '@order_msb\n'
                'struct Point:\n'
                '    x: int32\n'
                'func main() int32:\n'
                '    return 0\n',
                executable=False,
            )
        with self.assertRaisesRegex(CompilationError, 'potencia de dos'):
            self._compile(
                '@align(3)\n'
                'mold Invalid:\n'
                '    value: uint32\n'
                'func main() int32:\n'
                '    return 0\n',
                executable=False,
            )


if __name__ == '__main__':
    unittest.main()

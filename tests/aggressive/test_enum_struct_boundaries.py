from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class EnumStructBoundaryTests(unittest.TestCase):
    """Deep frontend/backend coverage for nominal enums and structs."""

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

    def test_enum_members_cover_signed_values_globals_calls_and_comparisons(self):
        code = (
            'enum Status int8:\n'
            '    UNKNOWN = -2,\n'
            '    READY = 3,\n'
            '    RUNNING,\n'
            'state: Status = Status.READY\n'
            'func identity(value: Status) Status:\n'
            '    return value\n'
            'func main() int32:\n'
            '    current: Status = identity(state)\n'
            '    if current != Status.READY:\n'
            '        return 1\n'
            '    if current < Status.RUNNING:\n'
            '        return 0\n'
            '    return 2\n'
        )
        self.assertEqual(0, self._run(code))

    def test_enum_unsigned_ordering_uses_the_underlying_unsigned_abi(self):
        self.assertEqual(
            0,
            self._run(
                'enum ByteCode uint8:\n'
                '    LOW = 250,\n'
                '    HIGH\n'
                'func main() int32:\n'
                '    if ByteCode.LOW < ByteCode.HIGH:\n'
                '        return 0\n'
                '    return 1\n'
            ),
        )

    def test_enum_duplicate_values_are_valid_but_names_are_not(self):
        self._compile(
            'enum Alias int8:\n'
            '    FIRST = 1,\n'
            '    ALSO_FIRST = 1\n'
            'func main() int32:\n'
            '    return 0\n',
            executable=False,
        )
        with self.assertRaisesRegex(CompilationError, 'miembro Alias.FIRST'):
            self._compile(
                'enum Alias:\n'
                '    FIRST,\n'
                '    FIRST\n'
                'func main() int32:\n'
                '    return 0\n',
                executable=False,
            )

    def test_enum_rejects_out_of_range_and_nominal_mixes(self):
        with self.assertRaisesRegex(CompilationError, 'fuera del rango'):
            self._compile(
                'enum Tiny int8:\n'
                '    TOO_BIG = 128\n'
                'func main() int32:\n'
                '    return 0\n',
                executable=False,
            )
        with self.assertRaisesRegex(CompilationError, 'no coincide con Second'):
            self._compile(
                'enum First uint8:\n'
                '    VALUE\n'
                'enum Second uint8:\n'
                '    VALUE\n'
                'func main() int32:\n'
                '    first: First = First.VALUE\n'
                '    second: Second = first\n'
                '    return 0\n',
                executable=False,
            )

    def test_nested_structs_arrays_and_enum_fields_round_trip(self):
        self.assertEqual(
            0,
            self._run(
                'enum Kind uint8:\n'
                '    EMPTY,\n'
                '    DATA = 4\n'
                'struct Point:\n'
                '    x: int32\n'
                '    y: int32\n'
                'struct Packet:\n'
                '    first: Point\n'
                '    second: Point\n'
                '    kind: Kind\n'
                'func main() int32:\n'
                '    packet: Packet\n'
                '    packet.first.x = 10\n'
                '    packet.first.y = 2\n'
                '    packet.second.x = 20\n'
                '    packet.second.y = 3\n'
                '    packet.kind = Kind.DATA\n'
                '    if packet.kind != Kind.DATA:\n'
                '        return 1\n'
                '    return packet.first.x + packet.first.y + packet.second.x + packet.second.y - 35\n'
            ),
        )

    def test_struct_designated_literals_can_nest_and_return_by_value(self):
        self.assertEqual(
            0,
            self._run(
                'struct Point:\n'
                '    x: int32\n'
                '    y: int32\n'
                'struct Box:\n'
                '    origin: Point\n'
                '    size: Point\n'
                'func make_box() Box:\n'
                '    return Box{\n'
                '        .origin = Point{ .x = 4, .y = 5 },\n'
                '        .size = Point{ .x = 10, .y = 20 },\n'
                '    }\n'
                'func main() int32:\n'
                '    box: Box = make_box()\n'
                '    return box.origin.x + box.origin.y + box.size.x + box.size.y - 39\n'
            ),
        )

    def test_struct_value_cycles_are_rejected(self):
        with self.assertRaisesRegex(CompilationError, 'Ciclo de agregados por valor'):
            self._compile(
                'struct Node:\n'
                '    next: Node\n'
                'func main() int32:\n'
                '    return 0\n',
                executable=False,
            )

    def test_struct_pointer_cycles_remain_valid(self):
        self._compile(
            'struct Node:\n'
            '    value: int32\n'
            '    next *: Node\n'
            'func main() int32:\n'
            '    return 0\n',
            executable=False,
        )

    def test_struct_rejects_duplicate_and_unknown_fields(self):
        with self.assertRaisesRegex(CompilationError, 'campo Point.x'):
            self._compile(
                'struct Point:\n'
                '    x: int32\n'
                '    x: int32\n'
                'func main() int32:\n'
                '    return 0\n',
                executable=False,
            )
        with self.assertRaisesRegex(CompilationError, 'no existe'):
            self._compile(
                'struct Point:\n'
                '    missing: Unknown\n'
                'func main() int32:\n'
                '    return 0\n',
                executable=False,
            )


if __name__ == '__main__':
    unittest.main()

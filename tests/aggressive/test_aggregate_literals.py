from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import Compiler


class AggregateLiteralIntegrationTests(unittest.TestCase):
    """Native and IR-level coverage for designated aggregate construction."""

    def _compile(self, source: str, *, executable: bool = True):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        return Compiler().compile(path, executable=executable)

    def test_dynamic_nested_literals_flags_molds_and_postfix_execute(self):
        artifacts = self._compile(
            "clause Optimizations 'prod'\n"
            'struct Pair:\n'
            '    left: int32\n'
            '    right: int32\n'
            '@packed\n'
            'struct Packet:\n'
            '    pair: Pair\n'
            '    tag: byte\n'
            'mold WordView:\n'
            '    word: int32\n'
            '    bytes: byte[4]\n'
            'flags State uint8:\n'
            '    enabled: uBint<1> = 1\n'
            '    mode: uBint<2> = 2\n'
            '    reserved: uBint<5> = 0\n'
            'func make_pair(seed: int32) Pair:\n'
            '    return Pair{ .right = seed + 2, .left = seed }\n'
            'func main() int32:\n'
            '    seed: int32 = 40\n'
            '    packet: Packet = Packet{\n'
            '        .tag = "A",\n'
            '        .pair = make_pair(seed),\n'
            '    }\n'
            '    view: WordView = WordView{ .word = packet.pair.right }\n'
            '    state: State = State{ .mode = 3 }\n'
            '    if Pair{ .left = 9, .right = 1 }.left != 9:\n'
            '        return 1\n'
            '    if packet.pair.left != 40:\n'
            '        return 2\n'
            '    if view.word != 42:\n'
            '        return 3\n'
            '    if state.enabled != 0:\n'
            '        return 4\n'
            '    if state.mode != 3:\n'
            '        return 5\n'
            '    return 0\n'
        )

        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr.decode())

    def test_designated_local_has_no_default_store_before_its_literal_store(self):
        ir_path = self._compile(
            'volatile struct Point:\n'
            '    x: int32\n'
            '    y: int32\n'
            'func make(value: int32) int32:\n'
            '    point: Point = Point{ .x = value, .y = 8 }\n'
            '    return point.x\n'
            'func main() int32:\n'
            '    return make(12)\n',
            executable=False,
        )
        module = Path(ir_path).read_text(encoding='utf-8')
        point_stores = [
            line for line in module.splitlines()
            if 'store' in line and 'point.addr' in line
        ]
        self.assertEqual(1, len(point_stores), module)
        self.assertNotIn('store %"__bg_', point_stores[0])

    def test_mold_literal_clears_inactive_bytes(self):
        artifacts = self._compile(
            'mold WordView:\n'
            '    word: int32\n'
            '    bytes: byte[4]\n'
            'func main() int32:\n'
            '    view: WordView = WordView{ .word = 1 }\n'
            '    if view.bytes[3] != 0:\n'
            '        return 1\n'
            '    return 0\n'
        )
        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr.decode())

    def test_signed_flags_literal_masks_its_active_field(self):
        artifacts = self._compile(
            'flags State uint8:\n'
            '    delta: Bint<3> = 0\n'
            '    privileged: uBint<1> = 0\n'
            '    reserved: uBint<4> = 0\n'
            'func main() int32:\n'
            '    state: State = State{ .delta = -1 }\n'
            '    if state.delta != -1:\n'
            '        return 1\n'
            '    if state.privileged != 0:\n'
            '        return 2\n'
            '    if state.reserved != 0:\n'
            '        return 3\n'
            '    return 0\n'
        )
        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr.decode())

    def test_imported_type_alias_resolves_its_nominal_layout(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / 'model.bg').write_text(
            'struct Point:\n'
            '    x: int32\n'
            '    y: int32\n',
            encoding='utf-8',
        )
        main = root / 'main.bg'
        main.write_text(
            'import { Point as ImportedPoint } from model\n'
            'func main() int32:\n'
            '    point: ImportedPoint = ImportedPoint{ .x = 4, .y = 9 }\n'
            '    if ImportedPoint{ .x = 1, .y = 9 }.y != 9:\n'
            '        return 1\n'
            '    return point.x + point.y\n',
            encoding='utf-8',
        )
        artifacts = Compiler().compile(main, executable=True)
        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(13, result.returncode, result.stderr.decode())


if __name__ == '__main__':
    unittest.main()

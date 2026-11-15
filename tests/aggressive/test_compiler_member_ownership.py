from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


_CONSUME = (
    'opaque Handle: int32\n'
    'func close_handle(handle: Handle) void:\n'
    '    return\n'
    '@consume\n'
    'func close(handle: Handle) void:\n'
    '    close_handle(handle)\n'
)


class CompilerMemberOwnershipTests(unittest.TestCase):
    """Adversarial place overlap rules for temporary ``unique`` loans."""

    def _compile(self, source: str) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'main.bg'
        path.write_text(source, encoding='utf-8')
        Compiler().compile(path, executable=False)

    def test_distinct_struct_fields_are_disjoint_unique_places(self):
        self._compile(
            'struct Pair:\n'
            '    left: int32[2]\n'
            '    right: int32[2]\n'
            'func split(left: unique int32[2], right: unique int32[2]) void:\n'
            '    left[0] = 1\n'
            '    right[0] = 2\n'
            'func main() int32:\n'
            '    pair: Pair\n'
            '    split(pair.left, pair.right)\n'
            '    return 0\n'
        )

    def test_mold_fields_always_overlap(self):
        with self.assertRaisesRegex(CompilationError, 'solapa los prestamos unique'):
            self._compile(
                'mold View:\n'
                '    left: int32[2]\n'
                '    right: int32[2]\n'
                'func split(left: unique int32[2], right: unique int32[2]) void:\n'
                '    return\n'
                'func main() int32:\n'
                '    view: View\n'
                '    split(view.left, view.right)\n'
                '    return 0\n'
            )

    def test_root_and_descendant_overlap(self):
        with self.assertRaisesRegex(CompilationError, 'solapa'):
            self._compile(
                'func split(left: unique int32[2], right: int32[2]) void:\n'
                '    return\n'
                'func main() int32:\n'
                '    data: int32[2] = {0, 0}\n'
                '    split(data, data)\n'
                '    return 0\n'
            )

    def test_opaque_field_cannot_be_consumed_twice(self):
        with self.assertRaisesRegex(CompilationError, 'esta closed'):
            self._compile(
                _CONSUME
                + 'struct Owner:\n'
                '    handle: Handle\n'
                'func main() int32:\n'
                '    owner: Owner\n'
                '    close(owner.handle)\n'
                '    close(owner.handle)\n'
                '    return 0\n'
            )

    def test_unconsumed_opaque_field_reports_a_leak(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'main.bg'
        path.write_text(
            'opaque Handle: int32\n'
            'struct Owner:\n'
            '    handle: Handle\n'
            'func main() int32:\n'
            '    owner: Owner\n'
            '    return 0\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        compiler.compile(path, executable=False)
        self.assertTrue(any('owner.handle' in warning for warning in compiler.warnings))

    def test_conditional_field_consumption_keeps_a_possible_leak(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'main.bg'
        path.write_text(
            _CONSUME
            + 'struct Owner:\n'
            '    handle: Handle\n'
            'func report(flag: bool) void:\n'
            '    owner: Owner\n'
            '    if flag:\n'
            '        close(owner.handle)\n'
            'func main() int32:\n'
            '    report(true)\n'
            '    return 0\n',
            encoding='utf-8',
        )
        compiler = Compiler()
        compiler.compile(path, executable=False)
        self.assertTrue(any('owner.handle' in warning for warning in compiler.warnings))

    def test_aggregate_resource_assignment_moves_the_owner(self):
        self._compile(
            _CONSUME
            + 'struct Owner:\n'
            '    handle: Handle\n'
            'func main() int32:\n'
            '    first: Owner\n'
            '    second: Owner = first\n'
            '    close(second.handle)\n'
            '    return 0\n'
        )


if __name__ == '__main__':
    unittest.main()

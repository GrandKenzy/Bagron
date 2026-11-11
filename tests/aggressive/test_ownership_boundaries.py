from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


_OPAQUE = 'opaque Handle: int32\n'
_CLOSE = _OPAQUE + '@consume\nfunc close_handle(handle: Handle) void:\n    return\n'


class OwnershipBoundaryTests(unittest.TestCase):
    """Adversarial ownership and borrow-checker cases for system code."""

    def compile_source(self, source: str, *, strict: bool = False) -> Compiler:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        compiler = Compiler()
        compiler.strict_ownership = strict
        compiler.compile(path, executable=False)
        return compiler

    def assert_compile_error(self, source: str, pattern: str, *, strict: bool = False):
        with self.assertRaisesRegex(CompilationError, pattern):
            self.compile_source(source, strict=strict)

    def test_ordinary_buffer_borrows_can_alias_and_mutate_without_transferring(self):
        compiler = self.compile_source(
            'func touch(first: buffer[], first_length: Len_t, '
            'second: buffer[], second_length: Len_t) void:\n'
            '    if first_length > 0:\n'
            '        first[0] = 7\n'
            '    if second_length > 0:\n'
            '        second[0] = 8\n'
            '    return\n'
            'func main() int32:\n'
            '    data: buffer[2] = 0\n'
            '    touch(data, data)\n'
            '    Del data\n'
            '    return 0\n'
        )
        self.assertFalse(any('fuga' in warning for warning in compiler.warnings))

    def test_unique_arguments_reject_same_region_twice(self):
        self.assert_compile_error(
            'func split(left: unique buffer[], left_length: Len_t, '
            'region_left: Region_t, right: unique buffer[], '
            'right_length: Len_t, region_right: Region_t) void:\n'
            '    return\n'
            'func main() int32:\n'
            '    data: buffer[4] = 0\n'
            '    split(data, data)\n'
            '    Del data\n'
            '    return 0\n',
            'solapa las regiones unique',
        )

    def test_unique_region_cannot_overlap_an_ordinary_argument(self):
        self.assert_compile_error(
            'func split(left: unique buffer[], left_length: Len_t, '
            'region: Region_t, right: buffer[], right_length: Len_t) void:\n'
            '    return\n'
            'func main() int32:\n'
            '    data: buffer[4] = 0\n'
            '    split(data, data)\n'
            '    Del data\n'
            '    return 0\n',
            'pasa right dentro de la Region_t unique de left',
        )

    def test_unique_borrow_does_not_consume_the_callers_buffer(self):
        compiler = self.compile_source(
            'func inspect(data: unique buffer[], length: Len_t, '
            'region: Region_t) void:\n'
            '    return\n'
            'func main() int32:\n'
            '    data: buffer[4] = 0\n'
            '    inspect(data)\n'
            '    data[0] = 3\n'
            '    Del data\n'
            '    return 0\n'
        )
        self.assertFalse(any('fuga' in warning for warning in compiler.warnings))

    def test_moved_opaque_descriptor_cannot_be_read_transferred_or_closed(self):
        for tail, pattern in (
            ('    close_handle(handle)\n', 'descriptor handle esta moved'),
            ('    copy: Handle = handle\n', 'descriptor handle esta moved'),
        ):
            with self.subTest(tail=tail):
                self.assert_compile_error(
                    _CLOSE
                    + 'func main() int32:\n'
                    + '    handle: Handle\n'
                    + '    moved: Handle = handle\n'
                    + tail
                    + '    close_handle(moved)\n'
                    + '    return 0\n',
                    pattern,
                )

    def test_borrowed_opaque_cannot_escape_as_a_return_value(self):
        self.assert_compile_error(
            _OPAQUE
            + 'func relay(handle: Handle) Handle:\n'
            + '    return handle\n'
            + 'func main() int32:\n'
            + '    return 0\n',
            'return requiere un descriptor owned',
        )

    def test_conditional_move_poison_is_conservative(self):
        self.assert_compile_error(
            _CLOSE
            + 'func main() int32:\n'
            + '    handle: Handle\n'
            + '    flag: int32 = 1\n'
            + '    if flag == 1:\n'
            + '        moved: Handle = handle\n'
            + '        close_handle(moved)\n'
            + '    close_handle(handle)\n'
            + '    return 0\n',
            'puede estar moved',
        )

    def test_both_ownership_paths_must_be_closed_for_strict_mode(self):
        self.assert_compile_error(
            _CLOSE
            + 'func main() int32:\n'
            + '    handle: Handle\n'
            + '    flag: int32 = 1\n'
            + '    if flag == 1:\n'
            + '        close_handle(handle)\n'
            + '    return 0\n',
            'fuga de recurso',
            strict=True,
        )
        compiler = self.compile_source(
            _CLOSE
            + 'func main() int32:\n'
            + '    handle: Handle\n'
            + '    if true:\n'
            + '        close_handle(handle)\n'
            + '    else:\n'
            + '        close_handle(handle)\n'
            + '    return 0\n',
            strict=True,
        )
        self.assertFalse(any('fuga' in warning for warning in compiler.warnings))

    def test_consuming_outer_opaque_in_a_loop_is_rejected(self):
        self.assert_compile_error(
            _CLOSE
            + 'func main() int32:\n'
            + '    handle: Handle\n'
            + '    index: int32 = 0\n'
            + '    while index < 1:\n'
            + '        close_handle(handle)\n'
            + '        index += 1\n'
            + '    return 0\n',
            'se cierra o transfiere dentro de un bucle',
        )


if __name__ == '__main__':
    unittest.main()

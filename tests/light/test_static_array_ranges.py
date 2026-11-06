import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class StaticArrayRangeTests(unittest.TestCase):
    def compile_source(self, source: str) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        source = source.rstrip() + '\n\nfunc main() int32:\n    return 0\n'
        path.write_text(source, encoding='utf-8')
        Compiler().compile(path, executable=False)

    def test_while_literal_bound_proves_fixed_array_index(self):
        self.compile_source(
            'func sum(values: int32[4], length: Len_t, size: Size_t) int32:\n'
            '    index: uint32 = 0\n'
            '    total: int32 = 0\n'
            '    while index < 4:\n'
            '        total += values[index]\n'
            '        index += 1\n'
            '    return total\n'
        )

    def test_numeric_for_bound_proves_fixed_array_index(self):
        self.compile_source(
            'func sum(values: int32[4], length: Len_t, size: Size_t) int32:\n'
            '    total: int32 = 0\n'
            '    for index: uint32 ran (0, 4, 1):\n'
            '        total += values[index]\n'
            '    return total\n'
        )

    def test_while_literal_bound_proves_local_fixed_array_index(self):
        self.compile_source(
            'func sum_local() int32:\n'
            '    values: int32[4] = {1, 2, 3, 4}\n'
            '    index: uint32 = 0\n'
            '    total: int32 = 0\n'
            '    while index < 4:\n'
            '        total += values[index]\n'
            '        index += 1\n'
            '    return total\n'
        )

    def test_numeric_for_bound_proves_local_fixed_array_index(self):
        self.compile_source(
            'func sum_local() int32:\n'
            '    values: int32[4] = {1, 2, 3, 4}\n'
            '    total: int32 = 0\n'
            '    for index: uint32 ran (0, 4, 1):\n'
            '        total += values[index]\n'
            '    return total\n'
        )

    def test_numeric_for_bound_proves_affine_fixed_array_index(self):
        self.compile_source(
            'func sum_offset() int32:\n'
            '    values: int32[3] = {1, 2, 3}\n'
            '    total: int32 = 0\n'
            '    for index: uint32 ran (1, 4, 1):\n'
            '        total += values[index - 1]\n'
            '    return total\n'
        )

    def test_bound_larger_than_array_is_not_accepted(self):
        with self.assertRaisesRegex(CompilationError, 'indice dinamico'):
            self.compile_source(
                'func bad(values: int32[4], length: Len_t, size: Size_t) int32:\n'
                '    index: uint32 = 0\n'
                '    while index < 5:\n'
                '        return values[index]\n'
                '    return 0\n'
            )

    def test_index_write_before_access_invalidates_bound(self):
        with self.assertRaisesRegex(CompilationError, 'indice dinamico'):
            self.compile_source(
                'func bad(values: int32[4], length: Len_t, size: Size_t) int32:\n'
                '    index: uint32 = 0\n'
                '    while index < 4:\n'
                '        index += 1\n'
                '        return values[index]\n'
                '    return 0\n'
            )


if __name__ == '__main__':
    unittest.main()

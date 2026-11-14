from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class CompilerMemberTests(unittest.TestCase):
    """Source compiler members and runtime length forwarding."""

    def _compile(self, source: str) -> str:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'main.bg'
        path.write_text(source, encoding='utf-8')
        return Path(Compiler().compile(path, executable=False)).read_text(
            encoding='utf-8'
        )

    def test_scalar_and_outer_array_element_size_compile(self):
        self._compile(
            'func main() int32:\n'
            '    value: int8 = 10\n'
            '    matrix: int32[2][3] = {{1, 2, 3}, {4, 5, 6}}\n'
            '    scalar_size: usize = value.<size>\n'
            '    row_size: usize = matrix.<size>\n'
            '    return 0\n'
        )

    def test_open_array_length_is_forwarded_without_source_parameter(self):
        ir = self._compile(
            'func length(values: int32[]) usize:\n'
            '    return values.<len>\n'
            'func relay(values: int32[]) usize:\n'
            '    return length(values)\n'
            'func main() int32:\n'
            '    values: int32[3] = {1, 2, 3}\n'
            '    result: usize = relay(values)\n'
            '    return 0\n'
        )
        self.assertIn('__bg_len_values', ir)

    def test_buffer_length_comes_from_descriptor(self):
        self._compile(
            'func length(data: buffer[]) usize:\n'
            '    return data.<len>\n'
            'func main() int32:\n'
            '    data: buffer[4] = 0\n'
            '    result: usize = length(data)\n'
            '    Del data\n'
            '    return 0\n'
        )

    def test_chain_length_is_added_only_when_a_body_needs_it(self):
        ir = self._compile(
            'func plain(text: chain) void:\n'
            '    return\n'
            'func measure(text: chain) usize:\n'
            '    return text.<len>\n'
            'func main() int32:\n'
            '    plain("ok")\n'
            '    count: usize = measure("ok")\n'
            '    return 0\n'
        )
        self.assertIn('__bg_len_text', ir)
        plain_line = next(line for line in ir.splitlines() if 'plain' in line and 'define' in line)
        self.assertNotIn('__bg_len_text', plain_line)

    def test_legacy_expansion_parameter_has_migration_diagnostic(self):
        with self.assertRaisesRegex(CompilationError, 'Len_t fue retirado'):
            self._compile(
                'func length(values: int32[], count: Len_t) usize:\n'
                '    return count\n'
                'func main() int32:\n    return 0\n'
            )

    def test_legacy_dot_len_has_migration_diagnostic(self):
        with self.assertRaisesRegex(CompilationError, 'usa .<len>'):
            self._compile(
                'func main() int32:\n'
                '    values: int32[2] = 0\n'
                '    return values.len\n'
            )


if __name__ == '__main__':
    unittest.main()

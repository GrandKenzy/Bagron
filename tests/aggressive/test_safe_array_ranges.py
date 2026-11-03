from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class SafeArrayRangeTests(unittest.TestCase):
    def _compile(self, source: str, *, executable: bool = False):
        source = "clause Optimizations 'dev'\n" + source
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        return Compiler().compile(path, executable=executable)

    def test_char_and_byte_arrays_accept_len_t_bounded_loops(self):
        artifacts = self._compile(
            'func fill(data: char[], length: Len_t, size: Size_t) void:\n'
            '    index: usize = 0\n'
            '    while index < length:\n'
            '        data[index] = "X"\n'
            '        index += 1\n'
            '    return\n'
            'func touch(data: byte[], length: Len_t, size: Size_t) void:\n'
            '    index: usize = 0\n'
            '    while index < length:\n'
            '        data[index] = 1\n'
            '        index += 1\n'
            '    return\n'
            'func main() int32:\n'
            '    chars: char[4] = "abc"\n'
            '    bytes: byte[3] = {1, 2, 3}\n'
            '    fill(chars)\n'
            '    touch(bytes)\n'
            '    return 6\n',
            executable=True,
        )
        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(6, result.returncode)

    def test_unbounded_dynamic_index_remains_rejected(self):
        with self.assertRaisesRegex(CompilationError, 'indice conocido'):
            self._compile(
                'func read(data: char[], length: Len_t, size: Size_t, index: usize) char:\n'
                '    return data[index]\n'
                'func main() int32:\n'
                '    return 0\n',
            )

    def test_if_len_t_bound_proves_a_dynamic_index(self):
        self._compile(
            'func read(data: char[], length: Len_t, size: Size_t, index: usize) char:\n'
            '    if index < length:\n'
            '        return data[index]\n'
            '    return "X"\n'
            'func main() int32:\n'
            '    return 0\n',
        )

    def test_loop_with_index_write_before_access_is_rejected(self):
        with self.assertRaisesRegex(CompilationError, 'indice conocido'):
            self._compile(
                'func read(data: char[], length: Len_t, size: Size_t) char:\n'
                '    index: usize = 0\n'
                '    while index < length:\n'
                '        index = length + 1\n'
                '        return data[index]\n'
                '    return "X"\n'
                'func main() int32:\n'
                '    return 0\n',
            )

    def test_forwarded_len_t_keeps_the_range_proof(self):
        self._compile(
            'func inner(data: char[], length: Len_t, size: Size_t) void:\n'
            '    index: usize = 0\n'
            '    while index < length:\n'
            '        data[index] = "X"\n'
            '        index += 1\n'
            '    return\n'
            'func outer(data: char[], length: Len_t, size: Size_t) void:\n'
            '    inner(data)\n'
            '    return\n'
            'func main() int32:\n'
            '    data: char[3] = "ab"\n'
            '    outer(data)\n'
            '    return 0\n',
        )
    def test_for_iterator_proves_bounds_for_open_arrays(self):
        self._compile(
            'func fill(data: char[], length: Len_t, size: Size_t) void:\n'
            '    for index: usize in data:\n'
            '        data[index] = "X"\n'
            '    return\n'
            'func main() int32:\n'
            '    data: char[3] = "ab"\n'
            '    fill(data)\n'
            '    return 0\n',
        )



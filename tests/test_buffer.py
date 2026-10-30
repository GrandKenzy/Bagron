from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class BufferTests(unittest.TestCase):
    def _compile(self, source: str, *, executable: bool = False):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        return Compiler().compile(path, executable=executable)

    def test_allocates_indexes_concatenates_and_deletes(self):
        module_path = self._compile(
            'func main() int32:\n'
            '    left: buffer[2] = {10, 20}\n'
            '    right: buffer[3] = {30, 40, 50}\n'
            '    all: buffer[] = left + right\n'
            '    index: uint32 = 4\n'
            '    result: int32 = 1\n'
            '    if all[index] == 50:\n'
            '        result = 7\n'
            '    Del all\n'
            '    Del left\n'
            '    Del right\n'
            '    return result\n',
        )
        module = Path(module_path).read_text(encoding='utf-8')
        self.assertIn('call i8* @"memcpy"', module)
        self.assertIn('icmp ult i64', module)
        self.assertIn('call void @"free"(i8*', module)

    def test_emits_runtime_descriptor_and_free(self):
        module_path = self._compile(
            'func main() int32:\n'
            '    datos: buffer[8 * 100] = 0\n'
            '    datos[799] = 1\n'
            '    Del (datos)\n'
            '    return 0\n'
        )
        module = Path(module_path).read_text(encoding='utf-8')
        self.assertIn('%"__bagron_buffer" = type {i8*, i64}', module)
        self.assertIn('call i8* @"malloc"(i64 800)', module)
        self.assertIn('call i8* @"memset"', module)
        self.assertIn('call void @"free"(i8*', module)
        self.assertIn('store %"__bagron_buffer" zeroinitializer', module)

    def test_rejects_buffer_copy_and_function_boundaries(self):
        with self.assertRaisesRegex(CompilationError, 'no puede copiar buffers'):
            self._compile(
                'func main() int32:\n'
                '    first: buffer[2] = 0\n'
                '    second: buffer[2] = 0\n'
                '    second = first\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'debe declarar Len_t'):
            self._compile(
                'func consume(data: buffer[4]) void:\n'
                '    return\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_len_t_expands_buffer_length_and_forwards(self):
        module_path = self._compile(
            'func consume(data: buffer[], length: Len_t) usize:\n'
            '    return length\n'
            'func relay(data: buffer[], length: Len_t) usize:\n'
            '    return consume(data)\n'
            'func main() int32:\n'
            '    data: buffer[4] = 0\n'
            '    result: usize = relay(data)\n'
            '    Del data\n'
            '    return 0\n'
        )
        module = Path(module_path).read_text(encoding='utf-8')
        self.assertIn(
            'define i64 @"consume"(%"__bagron_buffer" %"data", i64 %"length")',
            module,
        )
        self.assertIn(
            'define i64 @"relay"(%"__bagron_buffer" %"data", i64 %"length")',
            module,
        )
        self.assertRegex(
            module,
            r'call i64 @"consume"\(%"__bagron_buffer" %"\.\d+", '
            r'i64 %"\.\d+"\)',
        )

    def test_buffer_len_t_is_borrowed_and_size_t_is_rejected(self):
        with self.assertRaisesRegex(CompilationError, 'no puede liberar un buffer'):
            self._compile(
                'func consume(data: buffer[], length: Len_t) void:\n'
                '    Del data\n'
                '    return\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'Size_t.*buffer'):
            self._compile(
                'func consume(data: buffer[], length: Len_t, size: Size_t) void:\n'
                '    return\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_unique_buffer_requires_region_but_keeps_descriptor_abi(self):
        module_path = self._compile(
            'func consume(data: unique buffer[], length: Len_t, '
            'region: Region_t) void:\n'
            '    return\n'
            'func main() int32:\n'
            '    data: buffer[4] = 0\n'
            '    consume(data)\n'
            '    Del data\n'
            '    return 0\n'
        )
        module = Path(module_path).read_text(encoding='utf-8')
        self.assertIn(
            'define void @"consume"(%"__bagron_buffer" %"data", i64 %"length")',
            module,
        )
        self.assertNotIn('noalias', module.split('define void @"consume"', 1)[1].split('{', 1)[0])


if __name__ == '__main__':
    unittest.main()

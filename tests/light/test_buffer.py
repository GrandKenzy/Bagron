from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class BufferTests(unittest.TestCase):
    def _compile(
        self,
        source: str,
        *,
        executable: bool = False,
        optimization_profile: str | None = 'dev',
    ):
        if (
            optimization_profile is not None
            and 'clause Optimizations' not in source
        ):
            source = f"clause Optimizations '{optimization_profile}'\n" + source
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

    def test_rejects_buffer_overwrite_and_allows_plain_boundaries(self):
        with self.assertRaisesRegex(CompilationError, 'ya posee un recurso'):
            self._compile(
                'func main() int32:\n'
                '    first: buffer[2] = 0\n'
                '    second: buffer[2] = 0\n'
                '    second = first\n'
                '    return 0\n'
            )

        self._compile(
            'func consume(data: buffer[4]) void:\n'
            '    return\n'
            'func main() int32:\n'
            '    data: buffer[4] = 0\n'
            '    consume(data)\n'
            '    Del data\n'
            '    return 0\n'
        )

    def test_buffer_length_comes_from_the_descriptor_and_forwards(self):
        module_path = self._compile(
            'func consume(data: buffer[]) usize:\n'
            '    return data.<len>\n'
            'func relay(data: buffer[]) usize:\n'
            '    return consume(data)\n'
            'func main() int32:\n'
            '    data: buffer[4] = 0\n'
            '    result: usize = relay(data)\n'
            '    Del data\n'
            '    return 0\n'
        )
        module = Path(module_path).read_text(encoding='utf-8')
        self.assertRegex(
            module,
            r'define i64 @"?__bg_[^"\s]*_consume_[^"\s]*"?\(%"__bagron_buffer" %"data"\)',
        )
        self.assertRegex(
            module,
            r'define i64 @"?__bg_[^"\s]*_relay_[^"\s]*"?\(%"__bagron_buffer" %"data"\)',
        )
        self.assertRegex(
            module,
            r'call i64 @"?__bg_[^"\s]*_consume_[^"\s]*"?\(%"__bagron_buffer" %"\.\d+"\)',
        )

    def test_buffer_borrow_is_preserved_and_size_member_is_rejected(self):
        with self.assertRaisesRegex(CompilationError, 'no puede liberar un buffer'):
            self._compile(
                'func consume(data: buffer[]) void:\n'
                '    Del data\n'
                '    return\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, '<size> no aplica a chain ni buffer'):
            self._compile(
                'func consume(data: buffer[]) usize:\n'
                '    return data.<size>\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_owned_buffer_becomes_dead_after_del(self):
        with self.assertRaisesRegex(CompilationError, 'estado ya es dead'):
            self._compile(
                'func main() int32:\n'
                '    data: buffer[4] = 0\n'
                '    Del data\n'
                '    Del data\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'esta dead'):
            self._compile(
                'func main() int32:\n'
                '    data: buffer[4] = 0\n'
                '    Del data\n'
                '    value: byte = data[0]\n'
                '    return value\n'
            )

    def test_dead_state_is_conservative_across_branches(self):
        with self.assertRaisesRegex(CompilationError, 'esta dead'):
            self._compile(
                'func main() int32:\n'
                '    data: buffer[4] = 0\n'
                '    if true:\n'
                '        Del data\n'
                '    data[0] = 1\n'
                '    return 0\n'
            )

    def test_rejects_del_inside_loops(self):
        with self.assertRaisesRegex(CompilationError, 'dentro de un bucle'):
            self._compile(
                'func main() int32:\n'
                '    data: buffer[4] = 0\n'
                '    while true:\n'
                '        Del data\n'
                '    return 0\n'
            )

    def test_unique_buffer_keeps_the_descriptor_abi(self):
        module_path = self._compile(
            'func consume(data: unique buffer[]) void:\n'
            '    return\n'
            'func main() int32:\n'
            '    data: buffer[4] = 0\n'
            '    consume(data)\n'
            '    Del data\n'
            '    return 0\n'
        )
        module = Path(module_path).read_text(encoding='utf-8')
        self.assertRegex(
            module,
            r'define void @"?__bg_[^"\s]*_consume_[^"\s]*"?\(%"__bagron_buffer" %"data"\)',
        )
        header = next(
            line for line in module.splitlines()
            if line.startswith('define void') and '_consume_' in line
        )
        self.assertNotIn('noalias', header)


if __name__ == '__main__':
    unittest.main()


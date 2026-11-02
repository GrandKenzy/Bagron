from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class RecursionTests(unittest.TestCase):
    def compile_source(self, source: str, *, executable: bool = False):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        return Compiler().compile(path, executable=executable)

    def test_rejects_direct_non_tail_recursion_without_annotation(self):
        with self.assertRaisesRegex(CompilationError, 'recursividad.*@recursive'):
            self.compile_source(
                'func loop(value: int32) int32:\n'
                '    return loop(value + 1) + 1\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_rejects_mutual_recursion_without_annotation(self):
        with self.assertRaisesRegex(CompilationError, 'ciclo'):
            self.compile_source(
                'func first(value: int32) int32:\n'
                '    return second(value)\n'
                'func second(value: int32) int32:\n'
                '    return first(value)\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_rejects_three_function_cycle_without_annotation(self):
        with self.assertRaisesRegex(CompilationError, 'ciclo'):
            self.compile_source(
                'func first(value: int32) int32:\n'
                '    return second(value)\n'
                'func second(value: int32) int32:\n'
                '    return third(value)\n'
                'func third(value: int32) int32:\n'
                '    return first(value)\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_recursive_annotation_allows_non_tail_and_mutual_cycles(self):
        module_path = self.compile_source(
            '@recursive\n'
            'func first(value: int32) int32:\n'
            '    return second(value) + 1\n'
            '@recursive\n'
            'func second(value: int32) int32:\n'
            '    return first(value)\n'
            'func main() int32:\n'
            '    return 0\n'
        )

        module = Path(module_path).read_text(encoding='utf-8')
        self.assertIn('call i32 @second', module)
        self.assertIn('call i32 @first', module)

    def test_tail_recursion_reuses_one_llvm_frame(self):
        module_path = self.compile_source(
            'func countdown(value: int32) int32:\n'
            '    if value > 0:\n'
            '        return countdown(value - 1)\n'
            '    return 0\n'
            'func main() int32:\n'
            '    return countdown(8)\n'
        )

        module = Path(module_path).read_text(encoding='utf-8')
        countdown = module.split('define i32 @countdown', 1)[1]
        countdown = countdown.split('define ', 1)[0]
        self.assertIn('tail.recursive', countdown)
        self.assertNotIn('call i32 @countdown', countdown)

    def test_buffer_frames_require_explicit_recursive_annotation(self):
        with self.assertRaisesRegex(CompilationError, '@recursive'):
            self.compile_source(
                'func walk(data: buffer[], length: Len_t) int32:\n'
                '    if length == 0:\n'
                '        return 0\n'
                '    return walk(data)\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        self.compile_source(
            '@recursive\n'
            'func walk(data: buffer[], length: Len_t) int32:\n'
            '    if length == 0:\n'
            '        return 0\n'
            '    return walk(data)\n'
            'func main() int32:\n'
            '    return 0\n'
        )


if __name__ == '__main__':
    unittest.main()

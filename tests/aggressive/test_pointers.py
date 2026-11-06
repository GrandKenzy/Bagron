from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class PointerAndAddressTests(unittest.TestCase):
    def _compile(
        self,
        source: str,
        *,
        executable: bool = True,
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

    def test_local_pointer_nested_dereference_and_array_index(self):
        artifacts = self._compile(
            'func main() int32:\n'
            '    value: int32 = 10\n'
            '    pointer *: int32 = $value\n'
            '    pointer_pointer **: int32 = $pointer\n'
            '    ((pointer_pointer)) = 20\n'
            '    values: int32[] = {1, 2, 3}\n'
            '    values[1] = (pointer)\n'
            '    return values[1]\n'
        )

        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(20, result.returncode)

    def test_pointer_parameters_remain_usable_without_pointer_returns(self):
        module_path = self._compile(
            'value: int32 = 7\n'
            '@unsafe\n'
            'func read(pointer *: int32) int32:\n'
            '    return (pointer)\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    return read($value)\n',
            executable=False,
        )

        module = Path(module_path).read_text(encoding='utf-8')
        self.assertRegex(module, r'define i32 @"?__bg_[^"\s]*_fn_read_[^"\s]*"?\(i32\*')

        with self.assertRaisesRegex(CompilationError, 'no puede retornar punteros'):
            self._compile(
                'func identity(pointer *: int32) int32*:\n'
                '    return pointer\n'
                'func main() int32:\n'
                '    return 0\n',
                executable=False,
            )

    def test_void_pointer_uses_generic_llvm_pointer(self):
        module_path = self._compile(
            'func consume(pointer *: void) void:\n'
            '    return\n'
            'func main() int32:\n'
            '    value: int32 = 7\n'
            '    handle *: void = Null\n'
            '    consume($value)\n'
            '    consume(handle)\n'
            '    return 0\n',
            executable=False,
        )

        module = Path(module_path).read_text(encoding='utf-8')
        self.assertRegex(module, r'define void @"?__bg_[^"\s]*_fn_consume_[^"\s]*"?\(i8\*')

    def test_global_address_and_constant_gep(self):
        module_path = self._compile(
            'struct Point:\n'
            '    x: int32\n'
            '    y: int32\n'
            'point: Point\n'
            'values: int32[3] = {1, 2, 3}\n'
            'field *: int32 = $point.x\n'
            'element *: int32 = $values[1]\n'
            'func main() int32:\n'
            '    return (element) + (field)\n',
            executable=False,
        )

        module = Path(module_path).read_text(encoding='utf-8')
        self.assertRegex(module, r'getelementptr \(%"?__bg_[^"\s]*_type_Point_[^"\s]*"?,')
        self.assertIn('getelementptr ([3 x i32],', module)

    def test_null_dereference_is_trapped_and_local_address_cannot_escape(self):
        module_path = self._compile(
            'func main() int32:\n'
            '    pointer *: int32 = Null\n'
            '    return (pointer)\n',
            executable=False,
        )
        module = Path(module_path).read_text(encoding='utf-8')
        self.assertIn('call void @"llvm.trap"()', module)

        with self.assertRaisesRegex(CompilationError, 'no puede retornar'):
            self._compile(
                'func leak() int32*:\n'
                '    value: int32 = 1\n'
                '    return $value\n'
                'func main() int32:\n'
                '    return 0\n',
                executable=False,
            )

        with self.assertRaisesRegex(CompilationError, 'procedencia local'):
            self._compile(
                'struct Holder:\n'
                '    pointer *: int32\n'
                'func make() Holder:\n'
                '    value: int32 = 41\n'
                '    return Holder{ .pointer = $value }\n'
                'func main() int32:\n'
                '    item: Holder = make()\n'
                '    return (item.pointer)\n',
                executable=False,
            )

        with self.assertRaisesRegex(CompilationError, 'almacenamiento global'):
            self._compile(
                'struct Holder:\n'
                '    pointer *: int32\n'
                'saved: Holder = Holder{ .pointer = Null }\n'
                'func store() void:\n'
                '    value: int32 = 41\n'
                '    saved = Holder{ .pointer = $value }\n'
                '    return\n'
                'func main() int32:\n'
                '    store()\n'
                '    return (saved.pointer)\n',
                executable=False,
            )

    def test_ampersand_remains_bitwise_and(self):
        artifacts = self._compile(
            'func main() int32:\n'
            '    return 6 & 3\n'
        )
        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(2, result.returncode)

    def test_buffer_concatenation_guards_usize_overflow_before_malloc(self):
        module_path = self._compile(
            'func main() int32:\n'
            '    left: buffer[2] = 0\n'
            '    right: buffer[3] = 0\n'
            '    combined: buffer[] = left + right\n'
            '    Del combined\n'
            '    Del left\n'
            '    Del right\n'
            '    return 0\n',
            executable=False,
        )
        module = Path(module_path).read_text(encoding='utf-8')
        self.assertIn('buffer.concat.overflow', module)
        self.assertRegex(module, r'icmp ugt i64 .*buffer.remaining')
        self.assertIn('call void @"llvm.trap"()', module)

    def test_static_array_extent_overflow_is_rejected_before_llvm(self):
        with self.assertRaisesRegex(CompilationError, 'array estatico'):
            self._compile(
                'func main() int32:\n'
                '    data: byte[9223372036854775808]\n'
                '    return 0\n',
                executable=False,
            )

        with self.assertRaisesRegex(CompilationError, 'extension total'):
            self._compile(
                'func main() int32:\n'
                '    data: byte[4294967296][4294967296]\n'
                '    return 0\n',
                executable=False,
            )


if __name__ == '__main__':
    unittest.main()


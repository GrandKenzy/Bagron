from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class PointerAndAddressTests(unittest.TestCase):
    def _compile(self, source: str, *, executable: bool = True):
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

    def test_pointer_parameter_and_pointer_return_follow_llvm_types(self):
        module_path = self._compile(
            'value: int32 = 7\n'
            'func identity(pointer *: int32) int32*:\n'
            '    return pointer\n'
            '@unsafe\n'
            'func read(pointer *: int32) int32:\n'
            '    return (pointer)\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    return read(identity($value))\n',
            executable=False,
        )

        module = Path(module_path).read_text(encoding='utf-8')
        self.assertIn('define i32* @"identity"(i32*', module)
        self.assertIn('define i32 @"read"(i32*', module)

    def test_void_pointer_uses_generic_llvm_pointer(self):
        module_path = self._compile(
            'func consume(pointer *: void) void:\n'
            '    return\n'
            'func make() void*:\n'
            '    return Null\n'
            'func main() int32:\n'
            '    value: int32 = 7\n'
            '    handle *: void = make()\n'
            '    consume($value)\n'
            '    consume(handle)\n'
            '    return 0\n',
            executable=False,
        )

        module = Path(module_path).read_text(encoding='utf-8')
        self.assertIn('define void @"consume"(i8*', module)
        self.assertIn('define i8* @"make"()', module)

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
        self.assertIn('getelementptr (%"Point",', module)
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


if __name__ == '__main__':
    unittest.main()

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
            'func main() int:\n'
            '    value: int = 10\n'
            '    pointer *: int = $value\n'
            '    pointer_pointer **: int = $pointer\n'
            '    ((pointer_pointer)) = 20\n'
            '    values: int[] = {1, 2, 3}\n'
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
            'value: int = 7\n'
            'func identity(pointer *: int) int*:\n'
            '    return pointer\n'
            '@unsafe\n'
            'func read(pointer *: int) int:\n'
            '    return (pointer)\n'
            '@unsafe\n'
            'func main() int:\n'
            '    return read(identity($value))\n',
            executable=False,
        )

        module = Path(module_path).read_text(encoding='utf-8')
        self.assertIn('define i32* @"identity"(i32*', module)
        self.assertIn('define i32 @"read"(i32*', module)

    def test_global_address_and_constant_gep(self):
        module_path = self._compile(
            'struct Point:\n'
            '    x: int\n'
            '    y: int\n'
            'point: Point\n'
            'values: int[3] = {1, 2, 3}\n'
            'field *: int = $point.x\n'
            'element *: int = $values[1]\n'
            'func main() int:\n'
            '    return (element) + (field)\n',
            executable=False,
        )

        module = Path(module_path).read_text(encoding='utf-8')
        self.assertIn('getelementptr (%"Point",', module)
        self.assertIn('getelementptr ([3 x i32],', module)

    def test_null_dereference_is_trapped_and_local_address_cannot_escape(self):
        module_path = self._compile(
            'func main() int:\n'
            '    pointer *: int = Null\n'
            '    return (pointer)\n',
            executable=False,
        )
        module = Path(module_path).read_text(encoding='utf-8')
        self.assertIn('call void @"llvm.trap"()', module)

        with self.assertRaisesRegex(CompilationError, 'no puede retornar'):
            self._compile(
                'func leak() int*:\n'
                '    value: int = 1\n'
                '    return $value\n'
                'func main() int:\n'
                '    return 0\n',
                executable=False,
            )

    def test_ampersand_remains_bitwise_and(self):
        artifacts = self._compile(
            'func main() int:\n'
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

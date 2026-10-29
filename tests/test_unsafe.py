from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class UnsafeBoundaryTests(unittest.TestCase):
    def _compile(self, source: str, *, executable: bool = True):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        return Compiler().compile(path, executable=executable)

    def test_safe_function_can_forward_an_opaque_pointer(self):
        self._compile(
            'value: int32 = 7\n'
            'func identity(pointer *: int32) int32*:\n'
            '    return pointer\n'
            'func main() int32:\n'
            '    result *: int32 = identity($value)\n'
            '    return 0\n',
            executable=False,
        )

    def test_safe_function_cannot_dereference_opaque_pointer_parameter(self):
        with self.assertRaisesRegex(CompilationError, 'procedencia conocida'):
            self._compile(
                'func read(pointer *: int32) int32:\n'
                '    return (pointer)\n'
                'func main() int32:\n'
                '    return 0\n',
                executable=False,
            )

    def test_unsafe_function_can_dereference_pointer_parameter(self):
        artifacts = self._compile(
            '@unsafe\n'
            'func read(pointer *: int32) int32:\n'
            '    return (pointer)\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    value: int32 = 7\n'
            '    return read($value)\n'
        )
        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(7, result.returncode)

    def test_safe_function_cannot_call_unsafe_function(self):
        with self.assertRaisesRegex(CompilationError, 'no puede llamar'):
            self._compile(
                '@unsafe\n'
                'func raw() int32:\n'
                '    return 1\n'
                'func main() int32:\n'
                '    return raw()\n',
                executable=False,
            )

    def test_safe_standalone_call_cannot_call_unsafe_function(self):
        with self.assertRaisesRegex(CompilationError, 'no puede llamar'):
            self._compile(
                '@unsafe\n'
                'func raw() int32:\n'
                '    return 1\n'
                'func main() int32:\n'
                '    raw()\n'
                '    return 0\n',
                executable=False,
            )

    def test_unsafe_function_can_call_safe_function(self):
        artifacts = self._compile(
            'func add(a: int32, b: int32) int32:\n'
            '    return a + b\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    return add(2, 3)\n'
        )
        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(5, result.returncode)

    def test_safe_array_index_requires_compile_time_bounds(self):
        with self.assertRaisesRegex(CompilationError, 'indice conocido'):
            self._compile(
                'func main() int32:\n'
                '    data: int32[] = {1, 2, 3}\n'
                '    index: int32 = 1\n'
                '    return data[index]\n',
                executable=False,
            )

    def test_safe_array_index_checks_inferred_length(self):
        with self.assertRaisesRegex(CompilationError, 'fuera del rango'):
            self._compile(
                'func main() int32:\n'
                '    data: int32[] = {1, 2, 3}\n'
                '    return data[3]\n',
                executable=False,
            )

    def test_unsafe_array_index_can_be_dynamic(self):
        artifacts = self._compile(
            '@unsafe\n'
            'func main() int32:\n'
            '    data: int32[] = {1, 2, 3}\n'
            '    index: int32 = 1\n'
            '    return data[index]\n'
        )
        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(2, result.returncode)

    def test_safe_matrix_index_checks_every_dimension(self):
        artifacts = self._compile(
            'func main() int32:\n'
            '    data: int32[2][3] = {{1, 2, 3}, {4, 5, 6}}\n'
            '    return data[1][2]\n'
        )
        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(6, result.returncode)

    def test_safe_matrix_index_rejects_dynamic_inner_dimension(self):
        with self.assertRaisesRegex(CompilationError, 'indice conocido'):
            self._compile(
                'func main() int32:\n'
                '    data: int32[2][3] = {{1, 2, 3}, {4, 5, 6}}\n'
                '    index: int32 = 1\n'
                '    return data[0][index]\n',
                executable=False,
            )

    def test_unsafe_matrix_index_can_be_dynamic_at_each_dimension(self):
        artifacts = self._compile(
            '@unsafe\n'
            'func main() int32:\n'
            '    data: int32[2][3] = {{1, 2, 3}, {4, 5, 6}}\n'
            '    row: int32 = 1\n'
            '    column: int32 = 2\n'
            '    return data[row][column]\n'
        )
        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(6, result.returncode)

    def test_safe_raw_pointer_index_requires_unsafe(self):
        with self.assertRaisesRegex(CompilationError, 'punteros crudos'):
            self._compile(
                'func read(pointer *: int32) int32:\n'
                '    return pointer[0]\n'
                'func main() int32:\n'
                '    return 0\n',
                executable=False,
            )

    def test_standalone_call_is_validated_and_emitted(self):
        artifacts = self._compile(
            'func add(a: int32, b: int32) int32:\n'
            '    return a + b\n'
            'func main() int32:\n'
            '    add(1, 2)\n'
            '    return 0\n'
        )
        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(0, result.returncode)

    def test_assembler_is_also_unsafe_for_callers(self):
        with self.assertRaisesRegex(CompilationError, 'no puede llamar'):
            self._compile(
                '@assembler\n'
                'func raw() int32:\n'
                '    return 0\n'
                'func main() int32:\n'
                '    return raw()\n',
                executable=False,
            )


if __name__ == '__main__':
    unittest.main()

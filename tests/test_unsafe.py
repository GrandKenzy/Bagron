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
            'value: int = 7\n'
            'func identity(pointer *: int) int*:\n'
            '    return pointer\n'
            'func main() int:\n'
            '    result *: int = identity($value)\n'
            '    return 0\n',
            executable=False,
        )

    def test_safe_function_cannot_dereference_opaque_pointer_parameter(self):
        with self.assertRaisesRegex(CompilationError, 'procedencia conocida'):
            self._compile(
                'func read(pointer *: int) int:\n'
                '    return (pointer)\n'
                'func main() int:\n'
                '    return 0\n',
                executable=False,
            )

    def test_unsafe_function_can_dereference_pointer_parameter(self):
        artifacts = self._compile(
            '@unsafe\n'
            'func read(pointer *: int) int:\n'
            '    return (pointer)\n'
            '@unsafe\n'
            'func main() int:\n'
            '    value: int = 7\n'
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
                'func raw() int:\n'
                '    return 1\n'
                'func main() int:\n'
                '    return raw()\n',
                executable=False,
            )

    def test_safe_standalone_call_cannot_call_unsafe_function(self):
        with self.assertRaisesRegex(CompilationError, 'no puede llamar'):
            self._compile(
                '@unsafe\n'
                'func raw() int:\n'
                '    return 1\n'
                'func main() int:\n'
                '    raw()\n'
                '    return 0\n',
                executable=False,
            )

    def test_unsafe_function_can_call_safe_function(self):
        artifacts = self._compile(
            'func add(a: int, b: int) int:\n'
            '    return a + b\n'
            '@unsafe\n'
            'func main() int:\n'
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
                'func main() int:\n'
                '    data: int[] = {1, 2, 3}\n'
                '    index: int = 1\n'
                '    return data[index]\n',
                executable=False,
            )

    def test_safe_array_index_checks_inferred_length(self):
        with self.assertRaisesRegex(CompilationError, 'fuera del rango'):
            self._compile(
                'func main() int:\n'
                '    data: int[] = {1, 2, 3}\n'
                '    return data[3]\n',
                executable=False,
            )

    def test_unsafe_array_index_can_be_dynamic(self):
        artifacts = self._compile(
            '@unsafe\n'
            'func main() int:\n'
            '    data: int[] = {1, 2, 3}\n'
            '    index: int = 1\n'
            '    return data[index]\n'
        )
        result = subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(2, result.returncode)

    def test_safe_raw_pointer_index_requires_unsafe(self):
        with self.assertRaisesRegex(CompilationError, 'punteros crudos'):
            self._compile(
                'func read(pointer *: int) int:\n'
                '    return pointer[0]\n'
                'func main() int:\n'
                '    return 0\n',
                executable=False,
            )

    def test_standalone_call_is_validated_and_emitted(self):
        artifacts = self._compile(
            'func add(a: int, b: int) int:\n'
            '    return a + b\n'
            'func main() int:\n'
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
                'func raw() int:\n'
                '    return 0\n'
                'func main() int:\n'
                '    return raw()\n',
                executable=False,
            )


if __name__ == '__main__':
    unittest.main()

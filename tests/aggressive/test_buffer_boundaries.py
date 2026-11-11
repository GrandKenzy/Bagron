from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class BufferBoundaryTests(unittest.TestCase):
    """Stress the dynamic byte-buffer contract at compile and runtime edges."""

    def compile_source(self, source: str, *, executable: bool = False):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        return Compiler().compile(path, executable=executable)

    def run_source(self, source: str) -> subprocess.CompletedProcess[str]:
        artifacts = self.compile_source(source, executable=True)
        return subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
            text=True,
        )

    def assert_compile_error(self, source: str, pattern: str) -> None:
        with self.assertRaisesRegex(CompilationError, pattern):
            self.compile_source(source)

    def test_capacity_must_be_positive_and_compile_time_resolvable(self):
        for declaration in (
            'data: buffer[0] = 0\n',
            'data: buffer[-4] = 0\n',
            'data: buffer[true] = 0\n',
        ):
            with self.subTest(declaration=declaration):
                self.assert_compile_error(
                    'func main() int32:\n'
                    f'    {declaration}'
                    '    return 0\n',
                    'buffer|capacidad|tamano|entero',
                )

    def test_literal_initializers_cannot_change_the_declared_capacity(self):
        self.assert_compile_error(
            'func main() int32:\n'
            '    data: buffer[2] = {1, 2, 3}\n'
            '    return 0\n',
            'longitud|capacidad|no coincide|elementos',
        )
        self.assert_compile_error(
            'func main() int32:\n'
            '    data: buffer[3] = {1, 2}\n'
            '    return 0\n',
            'longitud|capacidad|no coincide|elementos',
        )

    def test_inferred_capacity_and_concatenation_preserve_all_bytes(self):
        result = self.run_source(
            'func main() int32:\n'
            '    left: buffer[2] = {10, 20}\n'
            '    right: buffer[3] = {30, 40, 50}\n'
            '    all: buffer[] = left + right\n'
            '    if all[0] != 10:\n'
            '        return 1\n'
            '    if all[2] != 30:\n'
            '        return 2\n'
            '    if all[4] != 50:\n'
            '        return 3\n'
            '    Del all\n'
            '    Del left\n'
            '    Del right\n'
            '    return 0\n'
        )
        self.assertEqual(0, result.returncode)

    def test_dynamic_out_of_bounds_access_traps_instead_of_becoming_pointer_arithmetic(self):
        result = self.run_source(
            'func main() int32:\n'
            '    data: buffer[2] = {1, 2}\n'
            '    index: uint32 = 2\n'
            '    value: byte = data[index]\n'
            '    return 0\n'
        )
        self.assertNotEqual(0, result.returncode)

    def test_buffer_parameters_require_only_len_and_are_borrowed(self):
        self.assert_compile_error(
            'func consume(data: buffer[]) void:\n'
            '    return\n'
            'func main() int32:\n'
            '    return 0\n',
            'debe declarar Len_t',
        )
        self.assert_compile_error(
            'func consume(data: buffer[], length: Len_t, size: Size_t) void:\n'
            '    return\n'
            'func main() int32:\n'
            '    return 0\n',
            'Size_t.*buffer',
        )
        self.assert_compile_error(
            'func consume(data: buffer[], length: Len_t) void:\n'
            '    Del data\n'
            '    return\n'
            'func main() int32:\n'
            '    return 0\n',
            'no puede liberar un buffer',
        )

    def test_buffer_cannot_be_copied_or_returned(self):
        self.assert_compile_error(
            'func make() buffer[2]:\n'
            '    data: buffer[2] = 0\n'
            '    return data\n'
            'func main() int32:\n'
            '    return 0\n',
            'buffer|retornar',
        )
        self.assert_compile_error(
            'func main() int32:\n'
            '    first: buffer[2] = 0\n'
            '    second: buffer[2] = 0\n'
            '    second = first\n'
            '    return 0\n',
            'no puede copiar buffers',
        )

    def test_del_is_terminal_across_parentheses_and_branches(self):
        self.assert_compile_error(
            'func main() int32:\n'
            '    data: buffer[4] = 0\n'
            '    Del (data)\n'
            '    data[0] = 1\n'
            '    return 0\n',
            'esta dead',
        )
        self.assert_compile_error(
            'func main() int32:\n'
            '    data: buffer[4] = 0\n'
            '    if true:\n'
            '        Del data\n'
            '    data[0] = 1\n'
            '    return 0\n',
            'esta dead',
        )

    def test_del_inside_a_loop_is_rejected_even_when_the_loop_looks_single_pass(self):
        self.assert_compile_error(
            'func main() int32:\n'
            '    data: buffer[1] = 0\n'
            '    index: uint32 = 0\n'
            '    while index < 1:\n'
            '        Del data\n'
            '        index += 1\n'
            '    return 0\n',
            'dentro de un bucle',
        )


if __name__ == '__main__':
    unittest.main()

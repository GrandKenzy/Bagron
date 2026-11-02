from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import Compiler


class ChainCharArrayConversionTests(unittest.TestCase):
    def compile_executable(self, source: str):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        try:
            artifacts = Compiler().compile(path, executable=True)
        except Exception:
            directory.cleanup()
            raise
        return directory, artifacts

    def test_explicit_copy_is_mutable_and_does_not_change_chain(self):
        source = (
            '@unsafe\n'
            'func main() int32:\n'
            '    text: chain = "hola"\n'
            '    buffer: char[] = text\n'
            '    buffer[0] = "X"\n'
            '    changed: char = "X"\n'
            '    if buffer[0] != changed:\n'
            '        return 1\n'
            '    original: char = "h"\n'
            '    if text[0] != original:\n'
            '        return 2\n'
            '    return 0\n'
        )
        directory, artifacts = self.compile_executable(source)
        try:
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )
        finally:
            directory.cleanup()
        self.assertEqual(0, result.returncode)

    def test_chain_literal_is_adapted_with_length_and_element_size(self):
        source = (
            '@unsafe\n'
            'func write(buffer: char[], length: Len_t, size: Size_t) int32:\n'
            '    if length == 1:\n'
            '        if size != 1:\n'
            '            return 1\n'
            '        return 0\n'
            '    if length != 5:\n'
            '        return 2\n'
            '    if size != 1:\n'
            '        return 3\n'
            '    expected: char = "h"\n'
            '    if buffer[0] != expected:\n'
            '        return 4\n'
            '    buffer[0] = "X"\n'
            '    changed: char = "X"\n'
            '    if buffer[0] != changed:\n'
            '        return 5\n'
            '    return 0\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    result: int32 = write("hola")\n'
            '    empty: int32 = write("")\n'
            '    if result != 0:\n'
            '        return result\n'
            '    return empty\n'
        )
        directory, artifacts = self.compile_executable(source)
        try:
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )
        finally:
            directory.cleanup()
        self.assertEqual(0, result.returncode)

if __name__ == '__main__':
    unittest.main()

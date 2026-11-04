from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class CompilerSafetyTests(unittest.TestCase):
    def compile_source(self, source: str, *, executable: bool = False):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        try:
            result = Compiler().compile(path, executable=executable)
            if executable:
                self.assertTrue(result.executable.exists())
            return result, directory
        except Exception:
            directory.cleanup()
            raise

    def test_byte_uint8_conversion_is_explicit_and_scalar_only(self):
        source = (
            'func main() int32:\n'
            '    raw: byte = 255\n'
            '    value: uint8 = raw as uint8\n'
            '    restored: byte = value as byte\n'
            '    return 0\n'
        )
        result, directory = self.compile_source(source, executable=True)
        try:
            completed = subprocess.run(
                [str(result.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(0, completed.returncode)
        finally:
            directory.cleanup()

        with self.assertRaisesRegex(CompilationError, 'conversion explicita'):
            self.compile_source(
                'func main() int32:\n'
                '    value: uint8 = 1\n'
                '    invalid: uint32 = value as uint32\n'
                '    return 0\n'
            )

    def test_unsigned_constant_arithmetic_wraps_at_width(self):
        source = (
            'func main() int32:\n'
            '    value: uint32 = 0xFFFFFFFF\n'
            '    wrapped: uint32 = value + 1\n'
            '    if wrapped == 0:\n'
            '        return 0\n'
            '    return 1\n'
        )
        result, directory = self.compile_source(source, executable=True)
        try:
            completed = subprocess.run(
                [str(result.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(0, completed.returncode)
        finally:
            directory.cleanup()

    def test_constant_shift_count_must_fit_operand_width(self):
        with self.assertRaisesRegex(CompilationError, 'desplazamiento'):
            self.compile_source(
                'func main() int32:\n'
                '    value: uint32 = 1\n'
                '    invalid: uint32 = value << 32\n'
                '    return 0\n'
            )

    def test_dynamic_shift_count_traps_before_llvm_shift(self):
        source = (
            'func main() int32:\n'
            '    value: uint32 = 1\n'
            '    count: uint32 = 32\n'
            '    ignored: uint32 = value << count\n'
            '    if ignored == 0:\n'
            '        return 0\n'
            '    return 1\n'
        )
        result, directory = self.compile_source(source, executable=True)
        try:
            self.assertIn('llvm.trap', result.ir.read_text(encoding='utf-8'))
            completed = subprocess.run(
                [str(result.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode)
        finally:
            directory.cleanup()

    def test_secure_clear_is_typed_and_emits_volatile_stores(self):
        source = (
            'func main() int32:\n'
            '    bytes: byte[4] = {1, 2, 3, 4}\n'
            '    buffer: buffer[4] = {5, 6, 7, 8}\n'
            '    secure_clear(bytes)\n'
            '    secure_clear(buffer)\n'
            '    return 0\n'
        )
        result, directory = self.compile_source(source, executable=True)
        try:
            ir_text = result.ir.read_text(encoding='utf-8')
            self.assertIn('store volatile i8 0', ir_text)
            completed = subprocess.run(
                [str(result.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(0, completed.returncode)
        finally:
            directory.cleanup()


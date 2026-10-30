from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class ExternTests(unittest.TestCase):
    def compile_source(self, source: str, *, executable: bool = False):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        try:
            result = Compiler().compile(path, executable=executable)
            return directory, result
        except Exception:
            directory.cleanup()
            raise

    def test_extern_emits_windows_signatures_and_calls(self):
        source = (
            "clause Arch 'auto'\n"
            "clause System 'windows'\n"
            'extern "kernel32":\n'
            '    GetStdHandle(nStdHandle: uint32) *: void\n'
            '    WriteFile(\n'
            '        hFile *: void,\n'
            '        lpBuffer *: const void,\n'
            '        nNumberOfBytesToWrite: uint32,\n'
            '        lpNumberOfBytesWritten *: uint32,\n'
            '        lpOverlapped *: void\n'
            '    ) int32\n'
            '    GetLastError() uint32\n'
            '    ExitProcess(uExitCode: uint32) void\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    handle *: void = GetStdHandle(0)\n'
            '    WriteFile(handle, Null, 0, Null, Null)\n'
            '    return 0\n'
        )

        directory, output = self.compile_source(source)
        try:
            module = Path(output).read_text(encoding='utf-8')
        finally:
            directory.cleanup()

        self.assertIn('declare i8* @"GetStdHandle"(i32', module)
        self.assertIn(
            'declare i32 @"WriteFile"(i8* %".1", i8* %".2", '
            'i32 %".3", i32* %".4", i8* %".5")',
            module,
        )
        self.assertIn('declare i32 @"GetLastError"()', module)
        self.assertIn('declare void @"ExitProcess"(i32 %".1")', module)
        self.assertIn('call i8* @"GetStdHandle"(i32 0)', module)
        self.assertIn('call i32 @"WriteFile"', module)

    def test_extern_adds_library_and_links_windows_call(self):
        source = (
            "clause Arch 'auto'\n"
            "clause System 'windows'\n"
            'extern "kernel32":\n'
            '    GetCurrentProcessId() uint32\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    pid: uint32 = GetCurrentProcessId()\n'
            '    return 0\n'
        )

        compiler = Compiler()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(source, encoding='utf-8')
            artifacts = compiler.compile(path, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual(['kernel32'], compiler.storage.native_links)

    def test_extern_accepts_llvm_floating_scalars(self):
        source = (
            'extern "kernel32":\n'
            '    HalfNative(value: middle) middle\n'
            '    FloatNative(value: float) float\n'
            '    DoubleNative(value: double) double\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    half: middle = HalfNative(1.0)\n'
            '    single: float = FloatNative(2.0)\n'
            '    wide: double = DoubleNative(3.0)\n'
            '    return 0\n'
        )

        directory, output = self.compile_source(source)
        try:
            module = Path(output).read_text(encoding='utf-8')
        finally:
            directory.cleanup()

        self.assertIn('declare half @"HalfNative"(half', module)
        self.assertIn('declare float @"FloatNative"(float', module)
        self.assertIn('declare double @"DoubleNative"(double', module)

    def test_extern_is_unsafe_from_safe_functions(self):
        with self.assertRaisesRegex(CompilationError, 'no puede llamar'):
            self.compile_source(
                'extern "kernel32":\n'
                '    GetCurrentProcessId() uint32\n'
                'func main() int32:\n'
                '    return 0\n'
                '    GetCurrentProcessId()\n'
            )

    def test_extern_rejects_arrays_and_duplicate_names(self):
        with self.assertRaisesRegex(CompilationError, 'no puede usar arrays'):
            self.compile_source(
                'extern "kernel32":\n'
                '    Bad(values: uint32[]) uint32\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'no puede usar Len_t'):
            self.compile_source(
                'extern "kernel32":\n'
                '    Native(values: char[], long: Len_t) void\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_imported_extern_keeps_module_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'native.bg').write_text(
                'extern "kernel32":\n'
                '    GetCurrentProcessId() uint32\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import native as n\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    pid: uint32 = n.GetCurrentProcessId()\n'
                '    return 0\n',
                encoding='utf-8',
            )

            module_path = Compiler().compile(main, executable=False)
            module = Path(module_path).read_text(encoding='utf-8')

        self.assertIn('declare i32 @"GetCurrentProcessId"()', module)
        self.assertIn('call i32 @"GetCurrentProcessId"()', module)

        with self.assertRaisesRegex(CompilationError, 'ya fue declarada'):
            self.compile_source(
                'extern "kernel32":\n'
                '    Same() int32\n'
                'extern "user32":\n'
                '    Same() int32\n'
                'func main() int32:\n'
                '    return 0\n'
            )


if __name__ == '__main__':
    unittest.main()

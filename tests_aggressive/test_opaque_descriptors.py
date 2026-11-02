from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class OpaqueDescriptorTests(unittest.TestCase):
    def compile_source(self, source: str):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        try:
            result = Compiler().compile(path, executable=False)
        except Exception:
            directory.cleanup()
            raise
        return directory, result

    def test_windows_opaque_descriptor_uses_pointer_abi_and_ownership(self):
        source = (
            "clause System 'windows'\n"
            'opaque WINDOWS_FILE_DESCRIPTOR: void*\n'
            'extern windows "kernel32":\n'
            '    GetStdHandle(nStdHandle: uint32) WINDOWS_FILE_DESCRIPTOR\n'
            '    CloseHandle(handle: WINDOWS_FILE_DESCRIPTOR) int32\n'
            '@unsafe\n'
            'func create_file() WINDOWS_FILE_DESCRIPTOR:\n'
            '    return GetStdHandle(0)\n'
            'func inspect_file(handle: WINDOWS_FILE_DESCRIPTOR) void:\n'
            '    return\n'
            'func close_file(handle: WINDOWS_FILE_DESCRIPTOR) void:\n'
            '    return\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    handle: WINDOWS_FILE_DESCRIPTOR = create_file()\n'
            '    inspect_file(handle)\n'
            '    close_file(handle)\n'
            '    return 0\n'
        )
        directory, result = self.compile_source(source)
        try:
            module = Path(result).read_text(encoding='utf-8')
        finally:
            directory.cleanup()

        self.assertIn('declare ptr @GetStdHandle(i32)', module)
        self.assertIn('declare i32 @CloseHandle(ptr)', module)
        self.assertIn('define ptr @create_file()', module)
        self.assertIn('define void @close_file(ptr', module)

    def test_opaque_descriptor_is_nominal_and_closed_once(self):
        with self.assertRaisesRegex(CompilationError, 'requiere un descriptor owned'):
            self.compile_source(
                'opaque LINUX_FILE_DESCRIPTOR: int32\n'
                'func close_file(handle: LINUX_FILE_DESCRIPTOR) void:\n'
                '    return\n'
                'func wrapper(handle: LINUX_FILE_DESCRIPTOR) void:\n'
                '    close_file(handle)\n'
                '    return\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'descriptor .*closed'):
            self.compile_source(
                'opaque LINUX_FILE_DESCRIPTOR: int32\n'
                'func close_file(handle: LINUX_FILE_DESCRIPTOR) void:\n'
                '    return\n'
                'func main() int32:\n'
                '    handle: LINUX_FILE_DESCRIPTOR\n'
                '    close_file(handle)\n'
                '    close_file(handle)\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'no coincide con int64'):
            self.compile_source(
                'opaque LINUX_FILE_DESCRIPTOR: int32\n'
                'func main() int32:\n'
                '    handle: LINUX_FILE_DESCRIPTOR\n'
                '    value: int64 = handle\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'no coincide con'):
            self.compile_source(
                'opaque WINDOWS_FILE_DESCRIPTOR: void*\n'
                'opaque LINUX_FILE_DESCRIPTOR: int32\n'
                'func take(handle: WINDOWS_FILE_DESCRIPTOR) void:\n'
                '    return\n'
                'func main() int32:\n'
                '    handle: LINUX_FILE_DESCRIPTOR = 7\n'
                '    take(handle)\n'
                '    return 0\n'
            )

    def test_opaque_descriptor_cannot_be_addressed_or_wrapped(self):
        with self.assertRaisesRegex(CompilationError, 'no puede convertirse en un puntero'):
            self.compile_source(
                'opaque WINDOWS_FILE_DESCRIPTOR: void*\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    handle: WINDOWS_FILE_DESCRIPTOR = Null\n'
                '    pointer *: void = $handle\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'no puede envolver'):
            self.compile_source(
                'opaque WINDOWS_FILE_DESCRIPTOR: void*\n'
                'func main() int32:\n'
                '    pointer *: WINDOWS_FILE_DESCRIPTOR = Null\n'
                '    return 0\n'
            )

    def test_opaque_representation_consumes_and_rejects_array_suffixes(self):
        for declaration in (
            'opaque TOKEN: int32[2]\n',
            'opaque TOKEN: int32[2][3]\n',
        ):
            with self.subTest(declaration=declaration):
                with self.assertRaisesRegex(CompilationError, 'no puede ser un array'):
                    self.compile_source(
                        declaration
                        + 'func main() int32:\n'
                        + '    return 0\n'
                    )

        with self.assertRaisesRegex(CompilationError, 'no puede ser const'):
            self.compile_source(
                'opaque TOKEN: const int32\n'
                'func main() int32:\n'
                '    return 0\n'
            )


if __name__ == '__main__':
    unittest.main()

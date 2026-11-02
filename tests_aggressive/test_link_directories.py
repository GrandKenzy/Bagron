from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from core.backend.llvm.links import (
    NativeLinkError,
    copy_runtime_files,
    resolve_native_links,
)
from core.compiler import Compiler
from core.backend.llvm import LLVMBackend


class NativeLinkDirectoryTests(unittest.TestCase):
    def test_windows_static_library_is_used_by_the_real_linker(self):
        clang = shutil.which('clang')
        llvm_ar = shutil.which('llvm-ar')
        if clang is None or llvm_ar is None:
            self.skipTest('clang y llvm-ar son necesarios para el enlace real')

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bins = root / 'bins'
            bins.mkdir()
            c_source = root / 'answer.c'
            object_file = root / 'answer.obj'
            library = bins / 'SDL3.lib'
            c_source.write_text(
                'int SDL3_answer(void) { return 42; }\n',
                encoding='utf-8',
            )
            compile_result = subprocess.run(
                [
                    clang,
                    '--target=x86_64-pc-windows-msvc',
                    '-c',
                    str(c_source),
                    '-o',
                    str(object_file),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if compile_result.returncode != 0:
                self.skipTest(
                    f'clang no puede producir COFF en este entorno: '
                    f'{compile_result.stderr}'
                )
            archive_result = subprocess.run(
                [llvm_ar, 'rc', str(library), str(object_file)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if archive_result.returncode != 0:
                self.skipTest(
                    f'llvm-ar no puede producir la biblioteca local: '
                    f'{archive_result.stderr}'
                )

            main = root / '_main.bg'
            main.write_text(
                '#link "./bins"\n'
                'clause System "windows"\n'
                'extern windows "SDL3":\n'
                '    SDL3_answer() int32\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    return SDL3_answer()\n',
                encoding='utf-8',
            )

            compiler = Compiler()
            compiler.compile(main, executable=False)
            self.assertEqual(['windows:SDL3'], compiler.storage.native_links)
            self.assertEqual([bins.resolve()], compiler.storage.native_link_dirs)
            artifacts = LLVMBackend().build(compiler.storage)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(42, result.returncode)

    def test_system_libraries_do_not_require_a_project_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'SDL3.lib').write_bytes(b'static archive placeholder')
            plan = resolve_native_links(
                ['windows:kernel32', 'windows:SDL3'],
                [root],
                'x86_64-pc-windows-msvc',
            )

        self.assertEqual((f'-L{root}',), plan.search_args)
        self.assertEqual(('-lkernel32', '-lSDL3'), plan.library_args)
        self.assertEqual((), plan.runtime_files)

    def test_linux_dynamic_library_is_copied_to_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build = root / 'build'
            build.mkdir()
            library = root / 'libSDL3.so'
            library.write_bytes(b'dynamic placeholder')

            plan = resolve_native_links(
                ['c:SDL3'],
                [root],
                'x86_64-unknown-linux-gnu',
            )
            copy_runtime_files(plan.runtime_files, build)

            self.assertEqual(library.read_bytes(), (build / library.name).read_bytes())
            self.assertIn(library, plan.runtime_files)

    def test_missing_library_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(NativeLinkError, 'No se encontro'):
                resolve_native_links(
                    ['windows:SDL3'],
                    [Path(directory)],
                    'x86_64-pc-windows-msvc',
                )

    def test_incompatible_library_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'SDL3.dll').write_bytes(b'windows dynamic placeholder')
            with self.assertRaisesRegex(NativeLinkError, 'incompatible'):
                resolve_native_links(
                    ['c:SDL3'],
                    [root],
                    'x86_64-unknown-linux-gnu',
                )

    def test_import_library_requires_its_dll(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = root / 'SDL3.lib'
            library.write_bytes(b'import library placeholder')
            with patch(
                'core.backend.llvm.links._windows_import_library',
                return_value=True,
            ):
                with self.assertRaisesRegex(NativeLinkError, 'Falta la DLL'):
                    resolve_native_links(
                        ['windows:SDL3'],
                        [root],
                        'x86_64-pc-windows-msvc',
                    )


if __name__ == '__main__':
    unittest.main()

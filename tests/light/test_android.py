import os
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import main as bagron_main
from core.compiler import CompilationError, Compiler


class AndroidCompilationTests(unittest.TestCase):
    @staticmethod
    def _write_main(root: Path, triple: str) -> Path:
        source = root / 'main.bg'
        source.write_text(
            'clause System "android"\n'
            f'clause Arch "{triple}"\n'
            'func main() int32:\n'
            '    return 0\n',
            encoding='utf-8',
        )
        return source

    def test_android_targets_emit_ir_without_ndk_resolution(self):
        for triple in ('aarch64-linux-android35', 'x86_64-linux-android35'):
            with self.subTest(triple=triple), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                compiler = Compiler()
                output = compiler.compile(
                    self._write_main(root, triple),
                    executable=False,
                )

                module = Path(output).read_text(encoding='utf-8')
                self.assertIn(f'target triple = "{triple}"', module)
                self.assertEqual('android', compiler.storage.system)
                self.assertEqual(triple, compiler.storage.architecture)

    def test_android_requires_an_explicit_supported_triple(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'main.bg'
            source.write_text(
                'clause System "android"\n'
                'clause Arch "aarch64"\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'target Android invalido'):
                Compiler().compile(source, executable=False)

    def test_android_rejects_an_api_below_the_minimum(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write_main(root, 'aarch64-linux-android19')

            with self.assertRaisesRegex(CompilationError, 'API Android 19'):
                Compiler().compile(source, executable=False)

    def test_android_requires_the_ndk_only_for_native_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write_main(root, 'aarch64-linux-android35')
            with mock.patch.dict(
                os.environ,
                {'ANDROID_NDK_HOME': '', 'ANDROID_NDK_ROOT': ''},
                clear=False,
            ):
                with self.assertRaisesRegex(CompilationError, 'ANDROID_NDK_HOME'):
                    Compiler().compile(source, executable=True)

    def test_imported_android_modules_must_match_the_full_triple(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper = root / 'helper.bg'
            helper.write_text(
                'clause System "android"\n'
                'clause Arch "aarch64-linux-android34"\n'
                'func value() int32:\n'
                '    return 1\n',
                encoding='utf-8',
            )
            source = root / 'main.bg'
            source.write_text(
                'clause System "android"\n'
                'clause Arch "aarch64-linux-android35"\n'
                'import helper\n'
                'func main() int32:\n'
                '    return helper.value()\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'incompatible con el target'):
                Compiler().compile(source, executable=False)

    def test_execute_rejects_cross_compiling_android_on_the_host(self):
        fake_compiler = mock.Mock()
        fake_compiler.storage.system = 'android'
        fake_compiler.warnings = []
        fake_compiler.compile.return_value = mock.Mock(
            executable=Path('build/android-program')
        )
        stderr = StringIO()

        with mock.patch.object(bagron_main, 'Compiler', return_value=fake_compiler):
            with redirect_stderr(stderr):
                result = bagron_main.main(['program.bg', '--execute'])

        self.assertEqual(1, result)
        self.assertIn('usa adb', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()

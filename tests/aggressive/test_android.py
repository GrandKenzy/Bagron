import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from core.compiler import Compiler


class AndroidNativeBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ndk = os.environ.get('ANDROID_NDK_HOME') or os.environ.get('ANDROID_NDK_ROOT')
        if not ndk or not Path(ndk).is_dir():
            raise unittest.SkipTest('ANDROID_NDK_HOME no esta configurado')
        cls.ndk_root = Path(ndk).resolve()
        cls.readobj = (
            cls.ndk_root
            / 'toolchains'
            / 'llvm'
            / 'prebuilt'
            / 'windows-x86_64'
            / 'bin'
            / 'llvm-readobj.exe'
        )
        if not cls.readobj.is_file():
            raise unittest.SkipTest('llvm-readobj del NDK no esta disponible')

    def test_builds_android_elf_for_both_supported_abis(self):
        for triple in ('aarch64-linux-android35', 'x86_64-linux-android35'):
            with self.subTest(triple=triple), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / 'main.bg'
                source.write_text(
                    'clause System "android"\n'
                    f'clause Arch "{triple}"\n'
                    'func main() int32:\n'
                    '    return 0\n',
                    encoding='utf-8',
                )

                artifacts = Compiler().compile(source, executable=True)
                self.assertTrue(artifacts.executable.is_file())
                self.assertFalse(artifacts.executable.suffix)

                result = subprocess.run(
                    [str(self.readobj), '--file-headers', str(artifacts.executable)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                expected_machine = (
                    'EM_AARCH64' if triple.startswith('aarch64') else 'EM_X86_64'
                )
                self.assertIn(expected_machine, result.stdout)


if __name__ == '__main__':
    unittest.main()

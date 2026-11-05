import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from core.backend.llvm.android_toolchain import (
    AndroidToolchainError,
    resolve_android_toolchain,
)


class AndroidToolchainTests(unittest.TestCase):
    def _fake_ndk(self, root: Path, triple: str):
        prebuilt = root / 'toolchains' / 'llvm' / 'prebuilt' / 'windows-x86_64'
        (prebuilt / 'bin').mkdir(parents=True)
        (prebuilt / 'bin' / 'clang.exe').touch()
        (prebuilt / 'bin' / 'ld.lld.exe').touch()
        architecture = triple.split('-', 1)[0]
        api = triple.rsplit('android', 1)[1]
        library_triple = f'{architecture}-linux-android'
        (prebuilt / 'sysroot' / 'usr' / 'lib' / library_triple / api).mkdir(
            parents=True
        )

    def test_resolves_aarch64_ndk_toolchain_from_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            triple = 'aarch64-linux-android35'
            self._fake_ndk(root, triple)
            with mock.patch.dict(os.environ, {'ANDROID_NDK_HOME': str(root)}, clear=False):
                toolchain = resolve_android_toolchain(triple)

        self.assertEqual(triple, toolchain.triple)
        self.assertEqual(35, toolchain.api_level)
        self.assertEqual('aarch64', toolchain.target.architecture)
        self.assertTrue(toolchain.clang.name == 'clang.exe')
        self.assertTrue(toolchain.ld_lld.name == 'ld.lld.exe')
        self.assertTrue(toolchain.sysroot.name == 'sysroot')
        self.assertIn('--target=aarch64-linux-android35', toolchain.clang_target_args)

    def test_resolves_x86_64_ndk_toolchain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            triple = 'x86_64-linux-android35'
            self._fake_ndk(root, triple)
            toolchain = resolve_android_toolchain(triple, ndk_home=root)
            api_library_exists = toolchain.api_library_dir.is_dir()

        self.assertEqual('x86_64', toolchain.target.architecture)
        self.assertEqual(35, toolchain.target.api_level)
        self.assertTrue(api_library_exists)

    def test_rejects_unsupported_android_triples(self):
        with self.assertRaisesRegex(AndroidToolchainError, 'Triple Android'):
            resolve_android_toolchain('armv7a-linux-androideabi35', ndk_home='.')
        with self.assertRaisesRegex(AndroidToolchainError, 'minimo'):
            resolve_android_toolchain('aarch64-linux-android19', ndk_home='.')

    def test_rejects_missing_ndk_environment(self):
        with mock.patch.dict(
            os.environ,
            {'ANDROID_NDK_HOME': '', 'ANDROID_NDK_ROOT': ''},
            clear=False,
        ):
            with self.assertRaisesRegex(AndroidToolchainError, 'ANDROID_NDK_HOME'):
                resolve_android_toolchain('aarch64-linux-android35')

    def test_rejects_ndk_without_api_library_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._fake_ndk(root, 'aarch64-linux-android34')
            with self.assertRaisesRegex(AndroidToolchainError, 'bibliotecas'):
                resolve_android_toolchain('aarch64-linux-android35', ndk_home=root)

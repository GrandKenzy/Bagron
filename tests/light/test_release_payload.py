"""Tests for the prebuilt (no-network) Bagron release installation path."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import installer
from core.version import BAGRON_VERSION
from tools.prepare_release_payload import prepare_payload
from tools.deduplicate_portable_python import write_manifest


class PrebuiltReleaseTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        (root / 'core').mkdir(parents=True)
        (root / 'core' / 'version.py').write_text(
            f"BAGRON_VERSION = {BAGRON_VERSION!r}\n", encoding='utf-8'
        )
        (root / 'tools').mkdir()
        (root / 'tools' / 'vscode').mkdir()
        (root / 'tools' / 'vscode' / 'bagron-language-support.vsix').write_bytes(b'fake-vsix')
        (root / 'vendor' / 'gram').mkdir(parents=True)
        (root / 'vendor' / 'llvmlite').mkdir()
        (root / 'vendor' / 'gram' / '.git').mkdir()
        (root / 'vendor' / 'gram' / '.git' / 'config').write_text('ignored')
        (root / 'main.py').write_text('print("sample")\n')
        (root / 'vnma.toml').write_text('[project]\nname="Bagron"\n')
        platform_name = 'windows' if os.name == 'nt' else 'linux'
        library_name = (
            'bagron_aot.dll' if platform_name == 'windows' else 'libbagron_aot.so'
        )
        aot = root / 'build' / 'aot'
        aot.mkdir(parents=True)
        library = aot / library_name
        library.write_bytes(b'fake-parser')
        (aot / 'gram_parser_manifest.json').write_text(
            '{"grammar_id": "0x1234"}', encoding='utf-8'
        )
        runtime = root / 'build' / 'portable-python'
        python_bin = runtime / (
            'python.exe' if platform_name == 'windows' else 'bin/python'
        )
        python_bin.parent.mkdir(parents=True)
        python_bin.write_bytes(b'fake-python')
        write_manifest(runtime, platform=platform_name)
        prebuilt_libraries = root / 'build' / 'prebuilt-libs'
        prebuilt_libraries.mkdir(parents=True)
        (prebuilt_libraries / 'gnulibrary.lib').write_bytes(b'fake-lib')
        payload = prepare_payload(
            root, root / 'build' / 'release-payload', platform_name=platform_name
        )
        return payload, runtime

    def test_payload_contains_compiler_and_matching_aot(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload, runtime = self._fixture(Path(temporary))
            info = json.loads(
                (payload / 'bagron-prebuilt.json').read_text(encoding='utf-8')
            )
            self.assertEqual(BAGRON_VERSION, info['bagron_version'])
            self.assertEqual('main', info['gram_branch'])
            self.assertTrue((payload / 'vendor' / 'gram').is_dir())
            self.assertTrue((payload / 'vendor' / 'llvmlite').is_dir())
            self.assertTrue((payload / 'main.py').is_file())
            self.assertEqual(
                b'fake-lib',
                (payload / 'libs' / 'gnulibrary.lib').read_bytes(),
            )
            self.assertTrue(
                (payload / 'tools' / 'vscode' / 'bagron-language-support.vsix').is_file()
            )
            self.assertFalse((payload / 'vendor' / 'gram' / '.git').exists())
            aot = payload / 'build' / 'aot' / info['aot_library']
            self.assertEqual(hashlib.sha256(aot.read_bytes()).hexdigest(),
                             info['aot_sha256'])
            self.assertTrue(runtime.exists())

    def test_installer_uses_embedded_payload_without_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload, runtime = self._fixture(root)
            target = root / 'installed'
            command_result = mock.Mock(
                returncode=0,
                stdout=f'Bagron {BAGRON_VERSION}\n',
                stderr='',
            )
            with mock.patch.object(installer.sys, 'frozen', True, create=True), \
                 mock.patch.object(installer, '_bundled_compiler_dir', return_value=payload), \
                 mock.patch.object(installer, '_bundled_python_dir', return_value=runtime), \
                 mock.patch.object(installer, '_fetch_from_github', side_effect=AssertionError('network')), \
                 mock.patch.object(installer, '_bootstrap_vnma', side_effect=AssertionError('pip')), \
                 mock.patch.object(installer, '_build_aot_parser', side_effect=AssertionError('rebuild')), \
                 mock.patch.object(installer, '_add_to_posix_user_path', return_value=True), \
                 mock.patch.object(installer, '_add_to_windows_user_path', return_value=True), \
                 mock.patch.object(installer.subprocess, 'run', return_value=command_result):
                code = installer.install(target)
            self.assertEqual(0, code)
            self.assertTrue((target / 'main.py').is_file())
            self.assertTrue((target / 'vendor' / 'gram').is_dir())
            self.assertEqual(
                b'fake-lib',
                (target / 'libs' / 'gnulibrary.lib').read_bytes(),
            )
            self.assertTrue((target / 'build' / 'aot' /
                             ('bagron_aot.dll' if os.name == 'nt'
                              else 'libbagron_aot.so')).is_file())
            self.assertTrue((target / 'bin' /
                             ('bagron.cmd' if os.name == 'nt'
                              else 'bagron')).is_file())

    def test_corrupt_aot_does_not_install(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload, runtime = self._fixture(root)
            info = json.loads(
                (payload / 'bagron-prebuilt.json').read_text(encoding='utf-8')
            )
            (payload / 'build' / 'aot' / info['aot_library']).write_bytes(b'corrupt')
            target = root / 'installed'
            with mock.patch.object(installer.sys, 'frozen', True, create=True), \
                 mock.patch.object(installer, '_bundled_compiler_dir', return_value=payload), \
                 mock.patch.object(installer, '_bundled_python_dir', return_value=runtime), \
                 mock.patch.object(installer, '_fetch_from_github', side_effect=AssertionError('network')):
                code = installer.install(target)
            self.assertNotEqual(0, code)
            self.assertFalse((target / 'main.py').exists())


if __name__ == '__main__':
    unittest.main()

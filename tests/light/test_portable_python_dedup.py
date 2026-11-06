"""Regression tests for aliases omitted from PyInstaller release payloads."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tools.deduplicate_portable_python import (
    MANIFEST_NAME, make_manifest, restore_aliases, verify_manifest, write_manifest,
)


def _simulate_pyinstaller_inputs(source: Path, destination: Path, aliases: dict) -> None:
    """Copy only files collected by the data list in bagron-installer.spec."""
    destination.mkdir(parents=True)
    for path in source.rglob('*'):
        relative = path.relative_to(source)
        if relative.as_posix() in aliases:
            continue
        if path.is_symlink():
            raise AssertionError('unregistered symlink in test input')
        target = destination / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


class PortablePythonDedupTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', 'requires symlinks')
    def test_linux_symlink_aliases_survive_packaging_and_restoration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'runtime'
            (source / 'bin').mkdir(parents=True)
            (source / 'lib').mkdir()
            (source / 'bin/python3.14').write_bytes(b'python-binary')
            (source / 'bin/python3').symlink_to('python3.14')
            (source / 'bin/python').symlink_to('python3')
            (source / 'lib/libpython3.14.so.1.0').write_bytes(b'python-library')
            (source / 'lib/libpython3.14.so').symlink_to('libpython3.14.so.1.0')
            (source / 'lib64').symlink_to('lib', target_is_directory=True)

            manifest = make_manifest(source, platform='linux')
            self.assertEqual('bin/python3.14', manifest['aliases']['bin/python'])
            self.assertEqual('bin/python3.14', manifest['aliases']['bin/python3'])
            self.assertEqual(
                'lib/libpython3.14.so.1.0',
                manifest['aliases']['lib/libpython3.14.so'],
            )
            self.assertEqual('lib', manifest['aliases']['lib64'])
            write_manifest(source, platform='linux')

            extracted = root / 'extracted'
            _simulate_pyinstaller_inputs(source, extracted, manifest['aliases'])
            self.assertFalse((extracted / 'bin/python').exists())
            self.assertEqual(manifest['aliases'], verify_manifest(
                extracted, expected_platform='linux'
            ))
            self.assertEqual(4, restore_aliases(extracted, platform='linux'))
            self.assertTrue((extracted / 'bin/python').is_symlink())
            self.assertEqual(b'python-binary', (extracted / 'bin/python').read_bytes())
            self.assertTrue(os.path.samefile(
                extracted / 'lib/libpython3.14.so',
                extracted / 'lib/libpython3.14.so.1.0',
            ))
            self.assertTrue((extracted / 'lib64').is_symlink())

    def test_linux_regular_duplicate_aliases_are_recorded(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / 'bin').mkdir()
            (source / 'lib').mkdir()
            for name in ('python', 'python3', 'python3.14'):
                (source / 'bin' / name).write_bytes(b'same-python-binary')
            for name in ('libpython3.14.so', 'libpython3.14.so.1.0'):
                (source / 'lib' / name).write_bytes(b'same-python-library')
            aliases = make_manifest(source, platform='linux')['aliases']
            self.assertEqual('bin/python3.14', aliases['bin/python'])
            self.assertEqual('bin/python3.14', aliases['bin/python3'])
            self.assertEqual(
                'lib/libpython3.14.so.1.0',
                aliases['lib/libpython3.14.so'],
            )

    def test_windows_identical_files_restore_as_hardlinks_or_copies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'runtime'
            source.mkdir()
            (source / 'python.exe').write_bytes(b'python-exe')
            (source / 'python3.exe').write_bytes(b'python-exe')
            (source / 'python314.exe').write_bytes(b'python-exe')
            (source / 'python314.dll').write_bytes(b'full-library')
            (source / 'python3.dll').write_bytes(b'different-library')
            (source / 'pip.exe').write_bytes(b'pip-contents')
            info = make_manifest(source, platform='windows')
            self.assertEqual('python.exe', info['aliases']['python3.exe'])
            self.assertEqual('python.exe', info['aliases']['python314.exe'])
            self.assertNotIn('python3.dll', info['aliases'])
            self.assertNotIn('pip.exe', info['aliases'])
            write_manifest(source, platform='windows')
            extracted = root / 'extracted'
            _simulate_pyinstaller_inputs(source, extracted, info['aliases'])
            self.assertEqual(2, restore_aliases(extracted, platform='windows'))
            self.assertEqual(b'python-exe', (extracted / 'python314.exe').read_bytes())
            # Filesystems without hardlinks may legitimately fall back
            # to copied aliases, while the onefile payload stays deduplicated.
            self.assertEqual(
                (extracted / 'python.exe').read_bytes(),
                (extracted / 'python314.exe').read_bytes(),
            )

    def test_windows_falls_back_to_copy_when_hardlinks_not_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'python'
            source.mkdir()
            (source / 'python.exe').write_bytes(b'python')
            (source / 'python3.exe').write_bytes(b'python')
            info = make_manifest(source, platform='windows')
            write_manifest(source, platform='windows')
            extracted = Path(temporary) / 'extracted'
            _simulate_pyinstaller_inputs(source, extracted, info['aliases'])
            with mock.patch('tools.deduplicate_portable_python.os.link',
                            side_effect=OSError('unsupported filesystem')):
                restore_aliases(extracted, platform='windows')
            self.assertEqual((extracted / 'python.exe').read_bytes(),
                             (extracted / 'python3.exe').read_bytes())

    def test_manifest_rejects_traversal_before_restoration(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            (runtime / 'python.exe').write_bytes(b'python')
            (runtime / MANIFEST_NAME).write_text(json.dumps({
                'format_version': 1,
                'platform': 'windows',
                'aliases': {'../outside.exe': 'python.exe'},
            }), encoding='utf-8')
            with self.assertRaises(ValueError):
                restore_aliases(runtime, platform='windows')
            self.assertFalse((runtime.parent / 'outside.exe').exists())

    @unittest.skipUnless(os.name == 'posix', 'requires symlinks')
    def test_runtime_symlink_escaping_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / 'runtime'
            runtime.mkdir()
            outside = root / 'outside'
            outside.write_bytes(b'unrelated')
            (runtime / 'python3').symlink_to(outside)
            with self.assertRaises(ValueError):
                make_manifest(runtime, platform='linux')


if __name__ == '__main__':
    unittest.main()

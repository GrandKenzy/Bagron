import tarfile
import tempfile
from pathlib import Path
import unittest
from unittest import mock

import installer
from tools.package_linux import build_package


class InstallerTests(unittest.TestCase):
    def test_posix_launchers_are_executable_and_preserve_caller_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            bin_dir = Path(directory) / 'bin'
            with mock.patch.object(installer.os, 'name', 'posix'):
                installer._create_launchers(bin_dir)

            for name in ('bagron', 'Bagron'):
                launcher = bin_dir / name
                self.assertTrue(launcher.is_file())
                if installer.os.name == 'posix':
                    self.assertTrue(launcher.stat().st_mode & 0o111)
                content = launcher.read_text(encoding='utf-8')
                self.assertIn('#!/usr/bin/env bash', content)
                self.assertIn('BAGRON_CALLER_DIR="$PWD"', content)
                self.assertIn('exec vnma run main.py "$@"', content)

    def test_installer_writes_current_version_to_vnma_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            installer._configure_vnma_toml(target)
            content = (target / 'vnma.toml').read_text(encoding='utf-8')
            self.assertIn('version = "1.0.3"', content)
            self.assertIn('branch = "main"', content)

    def test_linux_package_contains_runtime_files_without_build_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            output = build_package(
                Path(__file__).resolve().parents[2],
                Path(directory) / 'bagron.tar.gz',
            )
            with tarfile.open(output, 'r:gz') as archive:
                names = set(archive.getnames())

            self.assertIn('Bagron-1.0.3/installer.py', names)
            self.assertIn('Bagron-1.0.3/install.sh', names)
            self.assertTrue(
                any(name.rstrip('/') == 'Bagron-1.0.3/modules' for name in names)
            )
            self.assertNotIn('Bagron-1.0.3/vendor/', names)
            self.assertFalse(any('/build/' in name for name in names))


if __name__ == '__main__':
    unittest.main()

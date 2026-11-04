import tarfile
import tempfile
import zipfile
from pathlib import Path
import unittest
from unittest import mock

import installer
from tools.prepare_portable_python import _select_asset
from tools.package_linux import build_package
from tools.package_windows import build_package as build_windows_package


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
                self.assertIn('python_bin="$bagron_home/.runtime/bin/python"', content)
                self.assertIn('exec "$python_bin" -m vnma run main.py "$@"', content)

    def test_bootstrap_vnma_uses_a_private_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Bagron'
            runtime_dir = target / installer.LOCAL_RUNTIME_NAME
            if installer.os.name == 'nt':
                (runtime_dir / 'Scripts').mkdir(parents=True)
            runtime_python = installer._runtime_python_path(runtime_dir)
            vnma_path = installer._vnma_path(runtime_dir)
            calls = []

            def fake_run(command, **kwargs):
                text_command = [str(part) for part in command]
                calls.append(text_command)
                if '-m' in text_command and 'venv' in text_command:
                    runtime_python.parent.mkdir(parents=True, exist_ok=True)
                    runtime_python.touch()
                elif text_command[-2:] == ['--upgrade', 'vnma']:
                    vnma_path.parent.mkdir(parents=True, exist_ok=True)
                    vnma_path.touch()
                if text_command[-2:] == ['pip', '--version']:
                    return mock.Mock(returncode=1)
                return mock.Mock(returncode=0)

            with mock.patch.object(installer, '_find_system_python', return_value=['python']), mock.patch.object(
                installer.subprocess,
                'run',
                side_effect=fake_run,
            ):
                result = installer._bootstrap_vnma(target)

            self.assertEqual(vnma_path.resolve(), result)
            self.assertTrue(any(command[-2:] == ['--upgrade', 'vnma'] for command in calls))
            self.assertTrue(
                all(
                    'pip install' not in ' '.join(command) or str(target) in ' '.join(command)
                    for command in calls
                )
            )

    def test_windows_launchers_use_portable_python_root(self):
        with tempfile.TemporaryDirectory() as directory:
            bin_dir = Path(directory) / 'bin'
            with mock.patch.object(installer.os, 'name', 'nt'):
                installer._create_launchers(bin_dir)

            cmd_content = (bin_dir / 'Bagron.cmd').read_text(encoding='utf-8')
            ps1_content = (bin_dir / 'Bagron.ps1').read_text(encoding='utf-8')
            self.assertIn(r'.runtime\python.exe', cmd_content)
            self.assertIn('"%PYTHON%" -m vnma run main.py %*', cmd_content)
            self.assertIn(r'.runtime\python.exe', ps1_content)
            self.assertIn('& $python -m vnma run main.py @args', ps1_content)

    def test_installer_writes_current_version_to_vnma_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / 'vnma.lock').write_text('{"gram": "local"}', encoding='utf-8')
            installer._configure_vnma_toml(target)
            content = (target / 'vnma.toml').read_text(encoding='utf-8')
            self.assertIn('version = "1.0.3"', content)
            self.assertIn('https://github.com/GrandKenzy/Gram.git', content)
            self.assertNotIn('Desktop/Gram', content)
            self.assertIn('branch = "main"', content)
            self.assertFalse((target / 'vnma.lock').exists())

    def test_portable_python_builder_prefers_stripped_runtime(self):
        assets = [
            {
                'name': 'cpython-3.14.10+20261026-x86_64-pc-windows-msvc-install_only.tar.gz',
            },
            {
                'name': 'cpython-3.14.10+20261026-x86_64-pc-windows-msvc-install_only_stripped.tar.gz',
            },
        ]

        selected = _select_asset(assets, python_minor='3.14', target='windows')

        self.assertTrue(selected['name'].endswith('install_only_stripped.tar.gz'))

    def test_local_install_does_not_reuse_vnma_or_vendor_state(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            installer,
            '_bootstrap_vnma',
            return_value=None,
        ):
            target = Path(directory) / 'Bagron'
            result = installer.install(target, from_local=True)

            self.assertEqual(1, result)
            self.assertFalse((target / 'vendor').exists())
            self.assertFalse((target / 'bin').exists())
            config = (target / 'vnma.toml').read_text(encoding='utf-8')
            self.assertIn('https://github.com/GrandKenzy/Gram.git', config)

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
            aot_library = Path(__file__).resolve().parents[2] / 'build' / 'aot' / 'libbagron_aot.so'
            if aot_library.is_file():
                self.assertIn('Bagron-1.0.3/build/aot/libbagron_aot.so', names)
                self.assertIn('Bagron-1.0.3/build/aot/gram_parser_manifest.json', names)
            else:
                self.assertFalse(any('/build/' in name for name in names))

    def test_windows_package_contains_aot_runtime_when_available(self):
        source_root = Path(__file__).resolve().parents[2]
        if not (source_root / 'build' / 'aot' / 'bagron_aot.dll').is_file():
            self.skipTest('El runner no tiene el artefacto AOT de Windows')

        with tempfile.TemporaryDirectory() as directory:
            output = build_windows_package(source_root, Path(directory) / 'bagron.zip')
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())

            self.assertIn('Bagron-1.0.3/installer.py', names)
            self.assertIn('Bagron-1.0.3/build/aot/bagron_aot.dll', names)
            self.assertIn('Bagron-1.0.3/build/aot/gram_parser_manifest.json', names)
            self.assertFalse(any('/vendor/' in name for name in names))

    def test_release_publishes_only_compiled_installers(self):
        workflow = (Path(__file__).resolve().parents[2] / '.github' / 'workflows' / 'release.yml').read_text(
            encoding='utf-8'
        )
        linux_job = workflow.split('  package-linux:', 1)[1].split('  package-windows:', 1)[0]
        windows_job = workflow.split('  package-windows:', 1)[1].split('  publish:', 1)[0]
        publish_job = workflow.split('  publish:', 1)[1]
        source_root = Path(__file__).resolve().parents[2]
        self.assertTrue((source_root / 'bagron-installer.spec').is_file())
        self.assertTrue((source_root / 'tools' / 'prepare_portable_python.py').is_file())

        self.assertNotIn('package_linux.py', workflow)
        self.assertNotIn('package_windows.py', workflow)
        self.assertNotIn('.tar.gz', workflow)
        self.assertNotIn('.zip', workflow)
        self.assertNotIn('.vsix', workflow)
        self.assertIn('python -m pip install pyinstaller', linux_job)
        self.assertIn('python -m PyInstaller --clean --noconfirm', linux_job)
        self.assertIn('Bagron-${GITHUB_REF_NAME}-linux-x86_64', linux_job)
        self.assertIn('path: dist/Bagron-${{ github.ref_name }}-linux-x86_64', linux_job)
        self.assertIn('python -m pip install pyinstaller', windows_job)
        self.assertIn('python -m PyInstaller --clean --noconfirm', windows_job)
        self.assertIn('bagron-installer.spec', windows_job)
        self.assertIn('Bagron-${env:GITHUB_REF_NAME}-Setup.exe', windows_job)
        self.assertIn('path: dist/Bagron-${{ github.ref_name }}-Setup.exe', windows_job)
        self.assertIn('prepare_portable_python.py --platform linux', linux_job)
        self.assertIn('prepare_portable_python.py --platform windows', windows_job)
        self.assertIn('build/portable-python', linux_job)
        self.assertIn('build/portable-python', windows_job)
        self.assertIn('gh release delete-asset', publish_job)
        self.assertIn('--notes-file "$notes_file"', publish_job)

    def test_canonical_changelog_is_english_and_unique(self):
        changelog_dir = Path(__file__).resolve().parents[2] / 'changelog'
        canonical = changelog_dir / 'changelog_1.0.3.md'
        content = canonical.read_text(encoding='utf-8')

        self.assertTrue(content.startswith('# Changelog 1.0.3\n'))
        self.assertIn('## Modules and Linking', content)
        self.assertNotIn('Distribución Linux', content)
        self.assertEqual(
            ['changelog_1.0.3.md', 'changelog_1.0.4.md'],
            sorted(path.name for path in changelog_dir.iterdir()),
        )


if __name__ == '__main__':
    unittest.main()

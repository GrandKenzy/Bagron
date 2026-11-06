import os
import shutil
import subprocess
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
            (bin_dir / 'Bagron').parent.mkdir(parents=True)
            (bin_dir / 'Bagron').write_text('legacy launcher', encoding='utf-8')
            with mock.patch.object(installer.os, 'name', 'posix'):
                installer._create_launchers(bin_dir)

            launcher = bin_dir / 'bagron'
            self.assertEqual(['bagron'], sorted(path.name for path in bin_dir.iterdir()))
            self.assertTrue(launcher.is_file())
            if installer.os.name == 'posix':
                self.assertTrue(launcher.stat().st_mode & 0o111)
            content = launcher.read_text(encoding='utf-8')
            self.assertIn('#!/usr/bin/env bash', content)
            self.assertIn('BAGRON_CALLER_DIR="$PWD"', content)
            self.assertIn('while [[ -L "$launcher_path" ]]', content)
            self.assertIn('launcher_path="$(readlink "$launcher_path")"', content)
            self.assertIn('python_bin="$bagron_home/.runtime/bin/python"', content)
            self.assertIn('exec "$python_bin" -m vnma run main.py "$@"', content)

    @unittest.skipUnless(os.name == 'posix', 'requiere un entorno POSIX')
    def test_posix_launcher_resolves_installation_symlink(self):
        if shutil.which('bash') is None or shutil.which('readlink') is None:
            self.skipTest('requiere bash y readlink')

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Bagron'
            bin_dir = target / 'bin'
            runtime_python = target / '.runtime' / 'bin' / 'python'
            caller_dir = Path(directory) / 'caller'
            link_dir = Path(directory) / 'local' / 'bin'
            log_path = Path(directory) / 'launcher.log'

            installer._create_launchers(bin_dir)
            runtime_python.parent.mkdir(parents=True)
            caller_dir.mkdir()
            link_dir.mkdir(parents=True)
            runtime_python.write_text(
                '#!/usr/bin/env bash\n'
                'printf "%s\\n" "$PWD" > "$FAKE_BAGRON_LOG"\n'
                'printf "%s\\n" "$BAGRON_CALLER_DIR" >> "$FAKE_BAGRON_LOG"\n'
                'printf "%s\\n" "$*" >> "$FAKE_BAGRON_LOG"\n',
                encoding='utf-8',
            )
            runtime_python.chmod(0o755)
            link = link_dir / 'bagron'
            link.symlink_to(bin_dir / 'bagron')

            environment = os.environ.copy()
            environment['FAKE_BAGRON_LOG'] = str(log_path)
            result = subprocess.run(
                [str(link), '--probe'],
                cwd=caller_dir,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                [
                    str(target.resolve()),
                    str(caller_dir.resolve()),
                    '-m vnma run main.py --probe',
                ],
                log_path.read_text(encoding='utf-8').splitlines(),
            )

    def test_bootstrap_script_does_not_use_stdin_as_a_local_checkout(self):
        install_script = (
            Path(__file__).resolve().parents[2] / 'install.sh'
        ).read_text(encoding='utf-8')
        self.assertIn('script_source="${BASH_SOURCE[0]:-}"', install_script)
        self.assertIn('BAGRON_LOCAL_INSTALL:-0', install_script)
        self.assertIn('&& -n "$script_dir"', install_script)
        self.assertIn('&& -f "$script_dir/main.py"', install_script)
        self.assertIn('&& -d "$script_dir/core"', install_script)
        self.assertIn('&& -d "$script_dir/tools"', install_script)

    def test_bootstrap_vnma_uses_a_private_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Bagron'
            runtime_dir = target / installer.LOCAL_RUNTIME_NAME
            if installer.os.name == 'nt':
                (runtime_dir / 'Scripts').mkdir(parents=True)
            runtime_python = installer._runtime_python_path(runtime_dir)
            vnma_path = installer._vnma_path(runtime_dir)
            calls = []
            pip_enabled = False

            def fake_run(command, **kwargs):
                nonlocal pip_enabled
                text_command = [str(part) for part in command]
                calls.append(text_command)
                if '-m' in text_command and 'venv' in text_command:
                    runtime_python.parent.mkdir(parents=True, exist_ok=True)
                    runtime_python.touch()
                elif '-m' in text_command and 'ensurepip' in text_command:
                    pip_enabled = True
                elif text_command[-2:] == ['--upgrade', 'vnma']:
                    vnma_path.parent.mkdir(parents=True, exist_ok=True)
                    vnma_path.touch()
                if text_command[-2:] == ['pip', '--version']:
                    return mock.Mock(returncode=0 if pip_enabled else 1)
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

    def test_aot_parser_rebuilds_instead_of_reusing_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Bagron'
            output_dir = target / 'build' / 'aot'
            output_dir.mkdir(parents=True)
            stale_library = output_dir / installer._aot_library_names()[0]
            stale_manifest = output_dir / 'gram_parser_manifest.json'
            stale_library.write_bytes(b'stale library')
            stale_manifest.write_text('{"grammar_id": "0xdeadbeef"}', encoding='utf-8')

            calls = []

            def fake_run(command, **kwargs):
                command = [str(part) for part in command]
                calls.append(command)
                if any('build_aot_parser.py' in part for part in command):
                    output = Path(command[command.index('--output-dir') + 1])
                    output.mkdir(parents=True, exist_ok=True)
                    (output / installer._aot_library_names()[0]).write_bytes(b'fresh library')
                    (output / 'gram_parser_manifest.json').write_text(
                        '{"grammar_id": "0x1234"}',
                        encoding='utf-8',
                    )
                return mock.Mock(returncode=0)

            with mock.patch.object(installer.shutil, 'which', return_value='git'), mock.patch.object(
                installer.subprocess,
                'run',
                side_effect=fake_run,
            ):
                result = installer._build_aot_parser(target, Path('vnma'))

            self.assertTrue(result)
            self.assertEqual(b'fresh library', stale_library.read_bytes())
            self.assertEqual(2, len(calls))
            self.assertEqual('clone', calls[0][1])
            self.assertTrue(any('build_aot_parser.py' in part for part in calls[1]))

    def test_windows_launchers_use_portable_python_root(self):
        with tempfile.TemporaryDirectory() as directory:
            bin_dir = Path(directory) / 'bin'
            (bin_dir / 'Bagron').parent.mkdir(parents=True)
            (bin_dir / 'Bagron').write_text('legacy launcher', encoding='utf-8')
            with mock.patch.object(installer.os, 'name', 'nt'):
                installer._create_launchers(bin_dir)

            cmd_content = (bin_dir / 'bagron.cmd').read_text(encoding='utf-8')
            ps1_content = (bin_dir / 'bagron.ps1').read_text(encoding='utf-8')
            self.assertEqual(
                ['bagron.cmd', 'bagron.ps1'],
                sorted(path.name for path in bin_dir.iterdir()),
            )
            self.assertIn(r'.runtime\python.exe', cmd_content)
            self.assertIn(r'.runtime\Scripts\python.exe', cmd_content)
            self.assertIn('"%PYTHON%" -m vnma run main.py %*', cmd_content)
            self.assertIn(r'.runtime\python.exe', ps1_content)
            self.assertIn(r'.runtime\Scripts\python.exe', ps1_content)
            self.assertIn('& $python -m vnma run main.py @args', ps1_content)

    def test_installer_writes_current_version_to_vnma_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / 'vnma.lock').write_text('{"gram": "local"}', encoding='utf-8')
            installer._configure_vnma_toml(target)
            content = (target / 'vnma.toml').read_text(encoding='utf-8')
            self.assertIn('version = "1.1.1"', content)
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

            self.assertIn('Bagron-1.1.1/installer.py', names)
            self.assertIn('Bagron-1.1.1/install.sh', names)
            self.assertTrue(
                any(name.rstrip('/') == 'Bagron-1.1.1/modules' for name in names)
            )
            self.assertNotIn('Bagron-1.1.1/vendor/', names)
            self.assertFalse(any('/build/' in name for name in names))

    def test_windows_package_excludes_aot_runtime(self):
        source_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            output = build_windows_package(source_root, Path(directory) / 'bagron.zip')
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())

            self.assertIn('Bagron-1.1.1/installer.py', names)
            self.assertFalse(any('/build/' in name for name in names))
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
        canonical = changelog_dir / 'changelog_1.0.6.md'
        content = canonical.read_text(encoding='utf-8')

        self.assertTrue(content.startswith('# Changelog 1.0.6\n'))
        self.assertIn('## Assembler Function Contract', content)
        self.assertIn('## ABI and Backend Integration', content)
        self.assertIn('Released as Bagron `1.0.6`', content)
        names = sorted(path.name for path in changelog_dir.iterdir())
        self.assertIn('changelog_1.0.3.md', names)
        self.assertIn('changelog_1.0.4.md', names)
        self.assertIn('changelog_1.0.5.md', names)
        self.assertIn('changelog_1.0.6.md', names)
        self.assertIn('changelog_1.1.0.md', names)
        self.assertIn('changelog_1.1.1.md', names)
        self.assertEqual(
            6,
            sum(name.startswith('changelog_') for name in names),
        )


if __name__ == '__main__':
    unittest.main()

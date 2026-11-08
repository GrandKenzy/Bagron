import json
import io
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
            self.assertIn('installer.py" "$maintenance_command" --target', content)
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

    @unittest.skipUnless(os.name == 'nt', 'requiere Windows para ejecutar el helper .cmd')
    def test_windows_update_helper_runs_after_parent_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installer_path = root / 'downloaded.exe'
            installer_path.write_bytes(b'MZplaceholder')
            target = root / 'Bagron'
            target.mkdir()
            marker = root / 'marker.txt'
            fake_installer = root / 'fake-installer.cmd'
            fake_installer.write_text(
                '@echo off\r\n'
                f'echo installed>{marker}\r\n'
                'exit /b 0\r\n',
                encoding='utf-8',
            )
            with mock.patch.object(installer.subprocess, 'Popen'):
                self.assertTrue(installer._schedule_windows_update(installer_path, target))

            script = installer_path.with_suffix('.cmd')
            completed = subprocess.run(
                [
                    os.environ.get('ComSpec', 'cmd.exe'),
                    '/D',
                    '/C',
                    str(script),
                    str(fake_installer),
                    str(target),
                    '99999999',
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue(marker.is_file())

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

    def test_github_source_zip_rejects_traversal_before_extracting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'Bagron'
            archive_bytes = io.BytesIO()
            with zipfile.ZipFile(archive_bytes, 'w') as archive:
                archive.writestr(
                    f'Bagron-{installer.BAGRON_VERSION}/../../outside.txt',
                    b'unsafe',
                )

            response = mock.Mock()
            response.__enter__ = mock.Mock(return_value=response)
            response.__exit__ = mock.Mock(return_value=None)
            response.headers = {}
            response.read.side_effect = [archive_bytes.getvalue(), b'']
            with mock.patch.object(installer.shutil, 'which', return_value=None), \
                 mock.patch.object(installer, '_open_release_url', return_value=response):
                with self.assertRaises(OSError):
                    installer._fetch_from_github(target)

            self.assertFalse((root / 'outside.txt').exists())

    def test_github_source_zip_extracts_only_the_tagged_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'Bagron'
            archive_bytes = io.BytesIO()
            with zipfile.ZipFile(archive_bytes, 'w') as archive:
                archive.writestr(
                    f'Bagron-{installer.BAGRON_VERSION}/core/version.py',
                    'version = 1\n',
                )

            response = mock.Mock()
            response.__enter__ = mock.Mock(return_value=response)
            response.__exit__ = mock.Mock(return_value=None)
            response.headers = {}
            response.read.side_effect = [archive_bytes.getvalue(), b'']
            with mock.patch.object(installer.shutil, 'which', return_value=None), \
                 mock.patch.object(installer, '_open_release_url', return_value=response):
                installer._fetch_from_github(target)

            self.assertEqual(
                'version = 1\n',
                (target / 'core' / 'version.py').read_text(encoding='utf-8'),
            )

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

    def test_maintenance_commands_use_the_embedded_installer(self):
        with tempfile.TemporaryDirectory() as directory:
            bin_dir = Path(directory) / 'bin'
            with mock.patch.object(installer.os, 'name', 'nt'):
                installer._create_launchers(bin_dir)

            cmd_content = (bin_dir / 'bagron.cmd').read_text(encoding='utf-8')
            ps1_content = (bin_dir / 'bagron.ps1').read_text(encoding='utf-8')
            self.assertIn('installer.py" --update --target', cmd_content)
            self.assertIn('installer.py" --uninstall --target', cmd_content)
            self.assertIn('$args[0] -eq "--update"', ps1_content)
            self.assertIn('$args[0] -eq "--uninstall"', ps1_content)

    def test_update_uses_the_latest_github_asset_and_installed_version(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Bagron'
            version_file = target / 'core' / 'version.py'
            version_file.parent.mkdir(parents=True)
            version_file.write_text("BAGRON_VERSION = '1.1.2'\n", encoding='utf-8')
            commands = []

            def fake_download(url, destination):
                self.assertEqual('https://github.com/example/Bagron.exe', url)
                destination.write_bytes(installer._release_asset_magic() + b'installer')

            with mock.patch.object(
                installer, '_latest_release',
                return_value=('1.1.5', 'https://github.com/example/Bagron.exe'),
            ), mock.patch.object(
                installer, '_download_release_asset', side_effect=fake_download,
            ), mock.patch.object(
                installer.subprocess, 'run',
                side_effect=lambda command, **kwargs: commands.append(command) or mock.Mock(returncode=0),
            ):
                result = installer.update(target)

            self.assertEqual(0, result)
            self.assertEqual(1, len(commands))
            self.assertIn('--target', commands[0])
            self.assertEqual(
                target.resolve(),
                Path(commands[0][commands[0].index('--target') + 1]).resolve(),
            )

    def test_update_does_not_download_when_already_current(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Bagron'
            version_file = target / 'core' / 'version.py'
            version_file.parent.mkdir(parents=True)
            version_file.write_text("BAGRON_VERSION = '1.1.5'\n", encoding='utf-8')

            with mock.patch.object(
                installer, '_latest_release', return_value=('1.1.5', 'https://example.invalid/asset'),
            ), mock.patch.object(
                installer, '_download_release_asset', side_effect=AssertionError('download'),
            ):
                self.assertEqual(0, installer.update(target))

    def test_latest_release_selects_the_platform_asset(self):
        response = mock.Mock()
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=None)
        release_payload = json.dumps({
            'tag_name': 'v1.2.0',
            'assets': [
                {
                    'name': 'Bagron-1.2.0-Setup.exe',
                    'browser_download_url': 'https://github.com/GrandKenzy/Bagron/releases/download/v1.2.0/Bagron-1.2.0-Setup.exe',
                },
                {
                    'name': 'Bagron-1.2.0-linux-x86_64',
                    'browser_download_url': 'https://github.com/GrandKenzy/Bagron/releases/download/v1.2.0/Bagron-1.2.0-linux-x86_64',
                },
            ],
        }).encode('utf-8')
        response.read.side_effect = [release_payload, b'']

        with mock.patch.object(installer, '_open_release_url', return_value=response), \
             mock.patch.object(installer.os, 'name', 'nt'):
            self.assertEqual(
                ('1.2.0', 'https://github.com/GrandKenzy/Bagron/releases/download/v1.2.0/Bagron-1.2.0-Setup.exe'),
                installer._latest_release(),
            )

        response.read.side_effect = [release_payload, b'']
        with mock.patch.object(installer, '_open_release_url', return_value=response), \
             mock.patch.object(installer.os, 'name', 'posix'), \
             mock.patch.object(installer.sys, 'platform', 'linux'), \
             mock.patch.object(installer.platform, 'machine', return_value='x86_64'):
            self.assertEqual(
                ('1.2.0', 'https://github.com/GrandKenzy/Bagron/releases/download/v1.2.0/Bagron-1.2.0-linux-x86_64'),
                installer._latest_release(),
            )

    def test_latest_release_rejects_missing_platform_asset(self):
        response = mock.Mock()
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=None)
        response.read.side_effect = [
            json.dumps({'tag_name': '1.2.0', 'assets': []}).encode('utf-8'),
            b'',
        ]
        with mock.patch.object(installer, '_open_release_url', return_value=response), \
             mock.patch.object(installer.os, 'name', 'nt'):
            with self.assertRaises(FileNotFoundError):
                installer._latest_release()

    def test_release_asset_rejects_unpublished_platforms(self):
        with mock.patch.object(installer.os, 'name', 'nt'), \
             mock.patch.object(installer.platform, 'machine', return_value='ARM64'):
            with self.assertRaises(RuntimeError):
                installer._release_asset_name('1.1.5')

        with mock.patch.object(installer.os, 'name', 'posix'), \
             mock.patch.object(installer.sys, 'platform', 'linux'), \
             mock.patch.object(installer.platform, 'machine', return_value='aarch64'):
            with self.assertRaises(RuntimeError):
                installer._release_asset_name('1.1.5')

        with mock.patch.object(installer.os, 'name', 'posix'), \
             mock.patch.object(installer.sys, 'platform', 'darwin'):
            with self.assertRaises(RuntimeError):
                installer._release_asset_name('1.1.5')

    def test_update_reports_download_and_child_installer_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Bagron'
            (target / 'core').mkdir(parents=True)
            (target / 'core' / 'version.py').write_text(
                "BAGRON_VERSION = '1.1.2'\n", encoding='utf-8'
            )
            with mock.patch.object(
                installer, '_latest_release', return_value=('1.1.5', 'https://example.invalid/asset'),
            ), mock.patch.object(
                installer, '_download_release_asset', side_effect=OSError('network down'),
            ):
                self.assertEqual(1, installer.update(target))

            with mock.patch.object(
                installer, '_latest_release', return_value=('1.1.5', 'https://example.invalid/asset'),
            ), mock.patch.object(
                installer, '_download_release_asset',
                side_effect=lambda url, path: path.write_bytes(
                    installer._release_asset_magic() + b'installer'
                ),
            ), mock.patch.object(
                installer.subprocess, 'run', return_value=mock.Mock(returncode=23),
            ):
                self.assertEqual(23, installer.update(target))

    def test_windows_update_is_deferred_while_embedded_runtime_is_running(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Bagron'
            (target / 'core').mkdir(parents=True)
            (target / 'core' / 'version.py').write_text(
                "BAGRON_VERSION = '1.1.2'\n", encoding='utf-8'
            )
            with mock.patch.object(
                installer.os, 'name', 'nt'
            ), mock.patch.object(
                installer, '_latest_release', return_value=('1.1.5', 'https://example.invalid/asset'),
            ), mock.patch.object(
                installer, '_download_release_asset',
                side_effect=lambda url, path: path.write_bytes(
                    installer._release_asset_magic() + b'installer'
                ),
            ), mock.patch.object(
                installer, '_running_from_installation', return_value=True,
            ), mock.patch.object(
                installer, '_schedule_windows_update', return_value=True,
            ), mock.patch.object(
                installer.subprocess, 'run', side_effect=AssertionError('must defer'),
            ):
                self.assertEqual(0, installer.update(target))

    def test_windows_update_helper_has_no_visible_find_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installer_path = root / 'Bagron-1.1.5-Setup.exe'
            installer_path.write_bytes(b'MZinstaller')
            target = root / 'Bagron'
            target.mkdir()
            with mock.patch.object(installer.os, 'name', 'nt'), \
                 mock.patch.object(installer.os, 'getpid', return_value=8512), \
                 mock.patch.object(installer.subprocess, 'Popen') as popen, \
                 mock.patch.object(installer.subprocess, 'CREATE_NO_WINDOW', 0x08000000, create=True), \
                 mock.patch.object(installer.subprocess, 'DETACHED_PROCESS', 0x00000008, create=True):
                self.assertTrue(installer._schedule_windows_update(installer_path, target))

            script = installer_path.with_suffix('.cmd')
            content = script.read_text(encoding='utf-8')
            self.assertIn('tasklist.exe', content)
            self.assertIn('/FO CSV /NH', content)
            self.assertNotIn('find ', content.lower())
            flags = popen.call_args.kwargs['creationflags']
            self.assertEqual(0x08000000, flags)
            self.assertFalse(flags & 0x00000008)

    def test_posix_update_helper_waits_without_console_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installer_path = root / 'bagron-installer'
            installer_path.write_bytes(b'\x7fELFinstaller')
            target = root / 'Bagron'
            target.mkdir()
            with mock.patch.object(installer.os, 'name', 'posix'), \
                 mock.patch.object(installer.shutil, 'which', return_value='/bin/sh'), \
                 mock.patch.object(installer.subprocess, 'Popen') as popen, \
                 mock.patch.object(installer.os, 'getpid', return_value=8512):
                self.assertTrue(installer._schedule_posix_update(installer_path, target))

            script = installer_path.with_suffix('.sh')
            content = script.read_text(encoding='utf-8')
            self.assertIn('kill -0', content)
            self.assertNotIn('tasklist', content)
            self.assertEqual('/bin/sh', popen.call_args.args[0][0])

    def test_uninstall_removes_target_and_rejects_profile_root(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Bagron'
            (target / 'bin').mkdir(parents=True)
            (target / 'installer.py').write_text('installer', encoding='utf-8')
            with mock.patch.object(
                installer, '_remove_from_windows_user_path', return_value=True,
            ):
                self.assertEqual(0, installer.uninstall(target))
            self.assertFalse(target.exists())

        with mock.patch.object(installer.Path, 'home', return_value=Path(directory)):
            self.assertEqual(1, installer.uninstall(Path(directory)))

    def test_uninstall_schedules_windows_cleanup_when_runtime_is_locked(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'Bagron'
            target.mkdir()
            with mock.patch.object(
                installer, '_remove_from_windows_user_path', return_value=True,
            ), mock.patch.object(
                installer.shutil, 'rmtree', side_effect=OSError('runtime locked'),
            ), mock.patch.object(
                installer, '_schedule_windows_cleanup', return_value=True,
            ):
                self.assertEqual(0, installer.uninstall(target))

    def test_installer_writes_current_version_to_vnma_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / 'vnma.lock').write_text('{"gram": "local"}', encoding='utf-8')
            installer._configure_vnma_toml(target)
            content = (target / 'vnma.toml').read_text(encoding='utf-8')
            self.assertIn(f'version = "{installer.BAGRON_VERSION}"', content)
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
            (target / 'modules').mkdir(parents=True)
            (target / 'modules' / 'legacy.bg').write_text('legacy', encoding='utf-8')
            result = installer.install(target, from_local=True)

            self.assertEqual(1, result)
            self.assertFalse((target / 'vendor').exists())
            self.assertFalse((target / 'bin').exists())
            self.assertFalse((target / 'modules').exists())
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

            self.assertIn(f'Bagron-{installer.BAGRON_VERSION}/installer.py', names)
            self.assertIn(f'Bagron-{installer.BAGRON_VERSION}/install.sh', names)
            self.assertTrue(
                any(name.rstrip('/') == f'Bagron-{installer.BAGRON_VERSION}/libs' for name in names)
            )
            self.assertFalse(
                any(name.rstrip('/') == f'Bagron-{installer.BAGRON_VERSION}/modules' for name in names)
            )
            self.assertNotIn('Bagron-1.1.1/vendor/', names)
            self.assertFalse(any('/build/' in name for name in names))

    def test_windows_package_excludes_aot_runtime(self):
        source_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            output = build_windows_package(source_root, Path(directory) / 'bagron.zip')
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())

            self.assertIn(f'Bagron-{installer.BAGRON_VERSION}/installer.py', names)
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
        self.assertIn('Bagron-${PACKAGE_LABEL}-linux-x86_64', linux_job)
        self.assertIn('path: dist/Bagron-${{ env.PACKAGE_LABEL }}-linux-x86_64', linux_job)
        self.assertIn('python -m pip install pyinstaller', windows_job)
        self.assertIn('python -m PyInstaller --clean --noconfirm', windows_job)
        self.assertIn('bagron-installer.spec', windows_job)
        self.assertIn('Bagron-${env:PACKAGE_LABEL}-Setup.exe', windows_job)
        self.assertIn('path: dist/Bagron-${{ env.PACKAGE_LABEL }}-Setup.exe', windows_job)
        self.assertIn('prepare_portable_python.py --platform linux', linux_job)
        self.assertIn('prepare_portable_python.py --platform windows', windows_job)
        self.assertIn('build/portable-python', linux_job)
        self.assertIn('build/portable-python', windows_job)
        self.assertNotIn('repository: GrandKenzy/BagronLab', workflow)
        self.assertNotIn('Checkout BagronLab prebuilt libraries', workflow)
        self.assertNotIn('Stage BagronLab libraries', workflow)
        self.assertNotIn('build/prebuilt-libs', workflow)
        self.assertIn('Verify release payload has empty package directory', linux_job)
        self.assertIn('Verify release payload has empty package directory', windows_job)
        self.assertIn('tools/deduplicate_portable_python.py --platform linux', linux_job)
        self.assertIn('tools/deduplicate_portable_python.py --platform windows', windows_job)
        spec = (source_root / 'bagron-installer.spec').read_text(encoding='utf-8')
        self.assertIn('bagron-runtime-aliases.json', spec)
        self.assertIn('if relative in aliases:', spec)
        self.assertIn("if: startsWith(github.ref, 'refs/tags/')", publish_job)
        self.assertIn('workflow_dispatch:', workflow)
        self.assertIn('gh release delete-asset', publish_job)
        self.assertIn('--notes-file "$notes_file"', publish_job)

    def test_release_packaging_prepares_portable_vnma_and_gram_aot(self):
        workflow = (
            Path(__file__).resolve().parents[2]
            / '.github' / 'workflows' / 'release.yml'
        ).read_text(encoding='utf-8')

        linux_job = workflow.split('  package-linux:', 1)[1].split(
            '  package-windows:', 1
        )[0]
        windows_job = workflow.split('  package-windows:', 1)[1].split(
            '  publish:', 1
        )[0]

        for job, runtime, installer in (
            (linux_job, 'build/portable-python/bin/python', 'Build compiled Linux installer'),
            (windows_job, 'build/portable-python/python.exe', 'Build compiled Windows installer'),
        ):
            stages = (
                'Prepare portable Python runtime',
                'Install vnma in portable runtime',
                'Prepare vnma project configuration',
                'Resolve dependencies using portable runtime',
                'Checkout Gram native sources (main)',
                'Build Gram AOT parser',
                'Smoke test packaged compiler prerequisites',
                installer,
            )
            positions = [job.index(stage) for stage in stages]
            self.assertEqual(sorted(positions), positions)
            self.assertIn(f'{runtime} -m pip install --upgrade vnma', job)
            self.assertIn(f'{runtime} -m vnma install', job)
            self.assertIn(
                f'{runtime} -m vnma run tools/build_aot_parser.py', job
            )
            self.assertIn('git clone --depth 1 --branch main', job)
            self.assertIn('gram_parser_manifest.json', job)
            self.assertIn(f'{runtime} -m vnma run main.py', job)

        self.assertIn('libbagron_aot.so', linux_job)
        self.assertIn('bagron_aot.dll', windows_job)

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
        self.assertIn('changelog_1.1.2.md', names)
        self.assertIn('changelog_1.1.3.md', names)
        self.assertIn('changelog_1.1.4.md', names)
        self.assertIn('changelog_1.1.5.md', names)
        self.assertEqual(
            10,
            sum(name.startswith('changelog_') for name in names),
        )

    def test_bundled_vscode_extension_is_a_valid_vsix(self):
        vsix = Path(__file__).resolve().parents[2] / 'tools' / 'vscode' / 'bagron-language-support.vsix'
        with zipfile.ZipFile(vsix) as archive:
            names = set(archive.namelist())
            package = json.loads(archive.read('extension/package.json'))

        self.assertIn('extension.vsixmanifest', names)
        self.assertIn('extension/extension.js', names)
        self.assertIn('extension/syntaxes/bagron.tmLanguage.json', names)
        self.assertIn('extension/snippets/snippets.json', names)
        self.assertEqual('./extension.js', package['main'])
        self.assertEqual('bagron-language-support', package['name'])


if __name__ == '__main__':
    unittest.main()

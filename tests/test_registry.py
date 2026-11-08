import hashlib
import io
import json
import base64
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import MagicMock, patch
import urllib.error

from core.registry import (
    IntegrityError,
    PackageNotFoundError,
    RegistryError,
    download_package_artifact,
    install_package,
    list_installed_packages,
    pull_local_packages,
    resolve_package,
    search_packages,
    uninstall_package,
    update_package,
)
from core.library import pack_library, verify_library
from core.lockfile import LockfileError, update_lockfile
from core.signing import CentralSignatureError, verify_central_artifact


class TestRegistryClient(unittest.TestCase):
    def _library_bytes(self, name: str, version: str) -> bytes:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (source / 'main.bg').write_text(
                'public func answer() int32:\n'
                '    return 42\n',
                encoding='utf-8',
            )
            output = root / f'{name}.lib'
            pack_library(source, output, name=name, version=version)
            return output.read_bytes()

    def test_resolve_package_success(self):
        mock_response = io.BytesIO(json.dumps({
            'exists': True,
            'package': {
                'name': 'mathlib',
                'version': '1.2.0',
                'package_format': 'lib1',
                'artifact_checksum': 'sha256:abc123456789',
                'download_url': 'https://central.example.com/api/bagron/packages/mathlib/1.2.0/download',
            }
        }).encode('utf-8'))

        with patch('core.registry._open_url', return_value=mock_response):
            pkg = resolve_package('mathlib', '1.2.0', registry_url='https://central.example.com')
            self.assertEqual(pkg['name'], 'mathlib')
            self.assertEqual(pkg['version'], '1.2.0')
            self.assertEqual(pkg['package_format'], 'lib1')

    def test_resolve_package_not_found(self):
        err = urllib.error.HTTPError('https://central.example.com', 404, 'Not Found', {}, io.BytesIO(b'{"exists": false}'))
        with patch('core.registry._open_url', side_effect=err):
            with self.assertRaises(PackageNotFoundError):
                resolve_package('nonexistent', registry_url='https://central.example.com')

    def test_download_artifact_and_verify_checksum(self):
        content = b'BGLIB1\0\0dummy binary payload'
        content_sha = hashlib.sha256(content).hexdigest()

        mock_response = io.BytesIO(content)
        with patch('core.registry._open_url', return_value=mock_response):
            data = download_package_artifact(
                'https://central.example.com/download',
                expected_checksum=content_sha,
            )
            self.assertEqual(data, content)

    def test_download_artifact_integrity_failure(self):
        content = b'BGLIB1\0\0corrupted binary payload'
        mock_response = io.BytesIO(content)
        with patch('core.registry._open_url', return_value=mock_response):
            with self.assertRaises(IntegrityError):
                download_package_artifact(
                    'https://central.example.com/download',
                    expected_checksum='sha256:0000000000000000000000000000000000000000000000000000000000000000',
                )

    def test_download_requires_checksum_by_default(self):
        with self.assertRaises(IntegrityError):
            download_package_artifact('https://central.example.com/download')

    def test_download_rejects_non_https_url(self):
        with self.assertRaises(RegistryError):
            download_package_artifact(
                'http://central.example.com/download',
                expected_checksum='0' * 64,
            )

    def test_https_rejects_embedded_credentials_and_fragments(self):
        for url in (
            'https://user:password@central.example.com/pkg',
            'https://central.example.com/pkg#fragment',
            'https://central.example.com:invalid/pkg',
        ):
            with self.subTest(url=url), self.assertRaises(RegistryError):
                download_package_artifact(url, expected_checksum='0' * 64)

    def test_install_uses_real_resolver_and_keeps_central_credentials_on_origin(self):
        content = self._library_bytes('network', '2.0.0')
        package_info = {
            'name': 'network',
            'version': '2.0.0',
            'package_format': 'lib1',
            'artifact_checksum': hashlib.sha256(content).hexdigest(),
            'download_url': 'https://central.example.com/pkg/download',
        }
        resolve_response = io.BytesIO(json.dumps({
            'exists': True,
            'package': package_info,
        }).encode('utf-8'))
        download_response = io.BytesIO(content)

        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            'core.registry._open_url',
            side_effect=[resolve_response, download_response],
        ) as open_url:
            installed = install_package(
                'network@2.0.0',
                target_dir=Path(tmp_dir) / 'libs',
                registry_url='https://central.example.com',
            )
            self.assertTrue(installed.is_file())
            self.assertEqual(2, open_url.call_count)
            download_request = open_url.call_args_list[1].args[0]
            self.assertEqual(
                'bagron-cli',
                download_request.headers.get('X-central-client-id'),
            )

    def test_search_uses_secure_opener_and_validates_results(self):
        response = io.BytesIO(json.dumps({
            'data': [{
                'name': 'network',
                'latest_version': '2.0.0',
                'package_format': 'lib1',
                'description': 'Network helpers',
            }],
        }).encode('utf-8'))
        output: list[str] = []
        with patch('core.registry._open_url', return_value=response), patch(
            'core.registry.urllib.request.urlopen',
            side_effect=AssertionError('search bypassed the Central opener'),
        ):
            result = search_packages(
                'network',
                registry_url='https://central.example.com',
                print_fn=output.append,
            )

        self.assertEqual(0, result)
        self.assertTrue(any('network' in line for line in output))

    def test_search_rejects_invalid_result_schema(self):
        response = io.BytesIO(json.dumps({
            'packages': [{'name': '../outside', 'version': '1.0.0'}],
        }).encode('utf-8'))
        with patch('core.registry._open_url', return_value=response):
            with self.assertRaises(RegistryError):
                search_packages(registry_url='https://central.example.com')

    def test_install_rejects_path_traversal_name_from_registry(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dest = Path(tmp_dir) / 'libs'
            with patch(
                'core.registry.resolve_package',
                return_value={
                    'name': '../outside',
                    'version': '1.0.0',
                    'artifact_checksum': '0' * 64,
                    'download_url': 'https://central.example.com/download',
                },
            ), patch('core.registry.download_package_artifact') as download:
                with self.assertRaises(RegistryError):
                    install_package('network', target_dir=dest)
                download.assert_not_called()
            self.assertFalse((Path(tmp_dir) / 'outside.lib').exists())

    def test_install_allows_explicit_unverified_development_package(self):
        content = self._library_bytes('development', '0.1.0')
        resolve_payload = {
            'name': 'development',
            'version': '0.1.0',
            'package_format': 'lib1',
            'download_url': 'https://central.example.com/pkg/download',
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            dest = Path(tmp_dir) / 'libs'
            with patch('core.registry.resolve_package', return_value=resolve_payload), \
                 patch('core.registry.download_package_artifact', return_value=content):
                installed_file = install_package(
                    'development',
                    target_dir=dest,
                    allow_unverified=True,
                )
            self.assertTrue(installed_file.is_file())
            self.assertEqual(installed_file.read_bytes(), content)

    def test_package_install_creates_empty_target_directory_before_network(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / 'libs'
            with patch(
                'core.registry.resolve_package',
                side_effect=RegistryError('offline'),
            ):
                with self.assertRaises(RegistryError):
                    install_package('network', target_dir=target)
            self.assertTrue(target.is_dir())
            self.assertEqual([], list(target.iterdir()))

    def test_install_package_to_directory(self):
        content = self._library_bytes('network', '2.0.0')
        content_sha = hashlib.sha256(content).hexdigest()

        resolve_payload = {
            'exists': True,
            'package': {
                'name': 'network',
                'version': '2.0.0',
                'package_format': 'lib1',
                'artifact_checksum': content_sha,
                'download_url': 'https://central.example.com/pkg/download',
            }
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            dest = Path(tmp_dir) / 'libs'

            with patch('core.registry.resolve_package', return_value=resolve_payload['package']), \
                 patch('core.registry.download_package_artifact', return_value=content):
                installed_file = install_package(
                    'network@2.0.0',
                    target_dir=dest,
                    registry_url='https://central.example.com',
                    lockfile_path=Path(tmp_dir) / 'bagron.lock',
                )
                self.assertTrue(installed_file.is_file())
                self.assertEqual(installed_file.name, 'network.lib')
                self.assertEqual(installed_file.read_bytes(), content)
                lock = json.loads((Path(tmp_dir) / 'bagron.lock').read_text(encoding='utf-8'))
                self.assertEqual(content_sha, lock['packages']['network']['sha256'])

                # También soporta sintaxis con doble igual (==)
                installed_file_eq = install_package(
                    'network==2.0.0',
                    target_dir=dest,
                    registry_url='https://central.example.com',
                )
                self.assertTrue(installed_file_eq.is_file())

    def test_install_keeps_verified_existing_package_without_network(self):
        existing = self._library_bytes('network', '1.0.0')
        output: list[str] = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            dest = Path(tmp_dir) / 'libs'
            dest.mkdir()
            installed = (dest / 'network.lib').resolve()
            installed.write_bytes(existing)

            with patch(
                'core.registry.resolve_package',
                side_effect=AssertionError('install attempted a network request'),
            ):
                result = install_package('network@2.0.0', target_dir=dest, print_fn=output.append)

            self.assertEqual(installed, result)
            self.assertEqual(existing, installed.read_bytes())
            self.assertTrue(any('ya está instalado' in line for line in output))

    def test_update_explicitly_replaces_existing_package(self):
        old_content = self._library_bytes('network', '1.0.0')
        new_content = self._library_bytes('network', '2.0.0')
        payload = {
            'name': 'network',
            'version': '2.0.0',
            'package_format': 'lib1',
            'artifact_checksum': hashlib.sha256(new_content).hexdigest(),
            'download_url': 'https://central.example.com/pkg/download',
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            dest = Path(tmp_dir) / 'libs'
            dest.mkdir()
            installed = (dest / 'network.lib').resolve()
            installed.write_bytes(old_content)

            with patch('core.registry.resolve_package', return_value=payload), \
                 patch('core.registry.download_package_artifact', return_value=new_content):
                result = update_package('network', target_dir=dest)

            self.assertEqual(installed, result)
            self.assertEqual('2.0.0', verify_library(installed).manifest['version'])

    def test_pull_imports_verified_local_library_and_updates_lockfile(self):
        content = self._library_bytes('network', '1.0.0')
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = root / 'network.lib'
            source.write_bytes(content)
            target = (root / 'project' / 'libs').resolve()
            lock_path = root / 'project' / 'bagron.lock'

            imported = pull_local_packages(source, target_dir=target, lockfile_path=lock_path)

            self.assertEqual([target / 'network.lib'], imported)
            self.assertEqual(content, (target / 'network.lib').read_bytes())
            lock = json.loads(lock_path.read_text(encoding='utf-8'))
            self.assertEqual('1.0.0', lock['packages']['network']['version'])
            self.assertEqual('local:network.lib', lock['packages']['network']['source'])

    def test_pull_preserves_an_existing_verified_library(self):
        old_content = self._library_bytes('network', '1.0.0')
        new_content = self._library_bytes('network', '2.0.0')
        output: list[str] = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = root / 'network.lib'
            source.write_bytes(new_content)
            target = root / 'libs'
            target.mkdir()
            (target / 'network.lib').write_bytes(old_content)

            imported = pull_local_packages(source, target_dir=target, print_fn=output.append)

            self.assertEqual([], imported)
            self.assertEqual(old_content, (target / 'network.lib').read_bytes())
            self.assertTrue(any('no se reemplazó' in line for line in output))

    def test_list_reports_verified_local_packages(self):
        content = self._library_bytes('network', '1.0.0')
        output: list[str] = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / 'libs'
            target.mkdir()
            (target / 'network.lib').write_bytes(content)

            packages = list_installed_packages(target_dir=target, print_fn=output.append)

            self.assertEqual(1, len(packages))
            self.assertEqual(('network', '1.0.0', 'lib1'), packages[0][:3])
            self.assertTrue(any('network (v1.0.0, lib1)' in line for line in output))

    def test_uninstall_removes_package_and_lockfile_entry(self):
        content = self._library_bytes('network', '1.0.0')
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / 'libs'
            target.mkdir()
            installed = target / 'network.lib'
            installed.write_bytes(content)
            lock_path = root / 'bagron.lock'
            update_lockfile(
                lock_path,
                name='network',
                version='1.0.0',
                source='local:network.lib',
                package_format='lib1',
                data=content,
            )

            uninstall_package('network', target_dir=target, lockfile_path=lock_path)

            self.assertFalse(installed.exists())
            lock = json.loads(lock_path.read_text(encoding='utf-8'))
            self.assertNotIn('network', lock['packages'])

    def test_uninstall_preserves_package_required_by_a_locked_dependent(self):
        dependency = self._library_bytes('network', '1.0.0')
        application = self._library_bytes('application', '1.0.0')
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / 'libs'
            target.mkdir()
            installed = target / 'network.lib'
            installed.write_bytes(dependency)
            (target / 'application.lib').write_bytes(application)
            lock_path = root / 'bagron.lock'
            update_lockfile(
                lock_path,
                name='network',
                version='1.0.0',
                source='local:network.lib',
                package_format='lib1',
                data=dependency,
            )
            update_lockfile(
                lock_path,
                name='application',
                version='1.0.0',
                source='local:application.lib',
                package_format='lib1',
                data=application,
                dependencies=['network'],
            )

            with self.assertRaisesRegex(RegistryError, 'lo requieren'):
                uninstall_package('network', target_dir=target, lockfile_path=lock_path)

            self.assertEqual(dependency, installed.read_bytes())

    def test_invalid_artifact_does_not_replace_existing_package(self):
        valid = self._library_bytes('network', '1.0.0')
        invalid = b'BGLIB1\0\0not-a-package'
        with tempfile.TemporaryDirectory() as tmp_dir:
            dest = Path(tmp_dir) / 'libs'
            dest.mkdir()
            existing = dest / 'network.lib'
            existing.write_bytes(valid)
            payload = {
                'name': 'network',
                'version': '2.0.0',
                'package_format': 'lib1',
                'artifact_checksum': hashlib.sha256(invalid).hexdigest(),
                'download_url': 'https://central.example.com/pkg/download',
            }
            with patch('core.registry.resolve_package', return_value=payload), \
                 patch('core.registry.download_package_artifact', return_value=invalid):
                with self.assertRaises(RegistryError):
                    update_package('network', target_dir=dest)
            self.assertEqual(valid, existing.read_bytes())

    def test_lockfile_failure_rolls_back_package_replacement(self):
        old_content = self._library_bytes('network', '1.0.0')
        new_content = self._library_bytes('network', '2.0.0')
        payload = {
            'name': 'network',
            'version': '2.0.0',
            'package_format': 'lib1',
            'artifact_checksum': hashlib.sha256(new_content).hexdigest(),
            'download_url': 'https://central.example.com/pkg/download',
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            dest = Path(tmp_dir) / 'libs'
            dest.mkdir()
            existing = dest / 'network.lib'
            existing.write_bytes(old_content)
            with patch('core.registry.resolve_package', return_value=payload), \
                 patch('core.registry.download_package_artifact', return_value=new_content), \
                 patch(
                     'core.lockfile.update_lockfile',
                     side_effect=LockfileError('locked'),
                 ):
                with self.assertRaises(RegistryError):
                    update_package(
                        'network',
                        target_dir=dest,
                        lockfile_path=Path(tmp_dir) / 'bagron.lock',
                    )
            self.assertEqual(old_content, existing.read_bytes())

    def test_central_tuf_metadata_verifies_ed25519_statement(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key = Ed25519PrivateKey.generate()
        artifact = b'central artifact'
        signed = {
            '_type': 'targets',
            'version': 1,
            'expires': '2099-01-01T00:00:00Z',
            'target': {
                'name': 'network',
                'version': '2.0.0',
                'package_format': 'lib1',
                'length': len(artifact),
                'sha256': hashlib.sha256(artifact).hexdigest(),
            },
        }
        canonical = json.dumps(
            signed, ensure_ascii=False, sort_keys=True, separators=(',', ':')
        ).encode('utf-8')
        metadata = {
            'signed': signed,
            'signatures': [{
                'keyid': 'test-root',
                'sig': base64.b64encode(private_key.sign(canonical)).decode('ascii'),
            }],
        }
        with patch(
            'core.signing._trusted_keys',
            return_value={'test-root': private_key.public_key().public_bytes_raw()},
        ):
            self.assertTrue(verify_central_artifact(
                {'tuf': metadata},
                artifact,
                resolved_name='network',
                resolved_version='2.0.0',
                package_format='lib1',
                require=True,
            ))
            with self.assertRaisesRegex(CentralSignatureError, 'anteriores'):
                verify_central_artifact(
                    {'tuf': metadata},
                    artifact,
                    resolved_name='network',
                    resolved_version='2.0.0',
                    package_format='lib1',
                    require=True,
                    minimum_version=2,
                )

    def test_central_tuf_threshold_requires_distinct_trusted_signatures(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key = Ed25519PrivateKey.generate()
        artifact = b'central artifact'
        signed = {
            '_type': 'targets',
            'version': 1,
            'expires': '2099-01-01T00:00:00Z',
            'target': {
                'name': 'network',
                'version': '2.0.0',
                'package_format': 'lib1',
                'length': len(artifact),
                'sha256': hashlib.sha256(artifact).hexdigest(),
            },
        }
        canonical = json.dumps(
            signed, ensure_ascii=False, sort_keys=True, separators=(',', ':')
        ).encode('utf-8')
        metadata = {
            'signed': signed,
            'threshold': 2,
            'signatures': [{
                'keyid': 'test-root',
                'sig': base64.b64encode(private_key.sign(canonical)).decode('ascii'),
            }],
        }
        with patch(
            'core.signing._trusted_keys',
            return_value={'test-root': private_key.public_key().public_bytes_raw()},
        ):
            with self.assertRaisesRegex(CentralSignatureError, 'threshold'):
                verify_central_artifact(
                    {'tuf': metadata},
                    artifact,
                    resolved_name='network',
                    resolved_version='2.0.0',
                    package_format='lib1',
                    require=True,
                )

    def test_central_full_tuf_chain_verifies_roles_and_metadata_versions(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        private_key = Ed25519PrivateKey.generate()
        public_key = base64.b64encode(private_key.public_key().public_bytes_raw()).decode('ascii')

        def sign(signed: dict[str, object], key_id: str = 'root') -> dict[str, object]:
            canonical = json.dumps(
                signed, ensure_ascii=False, sort_keys=True, separators=(',', ':')
            ).encode('utf-8')
            return {
                'keyid': key_id,
                'sig': base64.b64encode(private_key.sign(canonical)).decode('ascii'),
            }

        roles = {
            role: {'keyids': ['root'], 'threshold': 1}
            for role in ('root', 'timestamp', 'snapshot', 'targets')
        }
        root_signed = {
            '_type': 'root',
            'version': 1,
            'expires': '2099-01-01T00:00:00Z',
            'keys': {'root': {
                'keytype': 'ed25519',
                'scheme': 'ed25519',
                'keyval': {'public': public_key},
            }},
            'roles': roles,
        }
        timestamp_signed = {
            '_type': 'timestamp',
            'version': 1,
            'expires': '2099-01-01T00:00:00Z',
            'meta': {'snapshot.json': {'version': 1}},
        }
        snapshot_signed = {
            '_type': 'snapshot',
            'version': 1,
            'expires': '2099-01-01T00:00:00Z',
            'meta': {'targets.json': {'version': 1}},
        }
        artifact = b'full tuf artifact'
        targets_signed = {
            '_type': 'targets',
            'version': 1,
            'expires': '2099-01-01T00:00:00Z',
            'targets': {
                'network/2.0.0.lib': {
                    'name': 'network',
                    'version': '2.0.0',
                    'package_format': 'lib1',
                    'length': len(artifact),
                    'hashes': {'sha256': hashlib.sha256(artifact).hexdigest()},
                },
            },
        }
        root_envelope = {
            'signed': root_signed,
            'signatures': [sign(root_signed, 'root')],
        }
        metadata = {
            'root': root_envelope,
            'timestamp': {'signed': timestamp_signed, 'signatures': [sign(timestamp_signed)]},
            'snapshot': {'signed': snapshot_signed, 'signatures': [sign(snapshot_signed)]},
            'targets': {'signed': targets_signed, 'signatures': [sign(targets_signed)]},
        }
        with patch(
            'core.signing._trusted_keys',
            return_value={'root': private_key.public_key().public_bytes_raw()},
        ), patch(
            'core.signing._trusted_roles',
            return_value={
                'root': {'keyids': ['root'], 'threshold': 1},
                'timestamp': {'keyids': ['root'], 'threshold': 1},
                'snapshot': {'keyids': ['root'], 'threshold': 1},
                'targets': {'keyids': ['root'], 'threshold': 1},
            },
        ):
            self.assertTrue(verify_central_artifact(
                {'tuf': metadata},
                artifact,
                resolved_name='network',
                resolved_version='2.0.0',
                package_format='lib1',
                require=True,
            ))

    def test_source_zip_rejects_path_traversal_before_install(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, 'w') as archive:
            archive.writestr('../outside.bg', b'public func bad() int32:\n    return 1\n')
        data = payload.getvalue()
        info = {
            'name': 'network',
            'version': '1.0.0',
            'package_format': 'lib1',
            'artifact_checksum': hashlib.sha256(data).hexdigest(),
            'download_url': 'https://central.example.com/pkg/download',
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / 'libs'
            with patch('core.registry.resolve_package', return_value=info), \
                 patch('core.registry.download_package_artifact', return_value=data):
                with self.assertRaises(RegistryError):
                    install_package('network', target_dir=target)
            self.assertFalse((Path(tmp_dir) / 'outside.bg').exists())

    def test_default_registry_url_is_discentra_net(self):
        from core.registry import DEFAULT_REGISTRY_URL
        self.assertEqual(DEFAULT_REGISTRY_URL, 'https://central.discentra.net')


if __name__ == '__main__':
    unittest.main()

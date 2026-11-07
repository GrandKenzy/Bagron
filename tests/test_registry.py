import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from core.registry import (
    IntegrityError,
    PackageNotFoundError,
    RegistryError,
    download_package_artifact,
    install_package,
    resolve_package,
)


class TestRegistryClient(unittest.TestCase):
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

        with patch('urllib.request.urlopen', return_value=mock_response):
            pkg = resolve_package('mathlib', '1.2.0', registry_url='https://central.example.com')
            self.assertEqual(pkg['name'], 'mathlib')
            self.assertEqual(pkg['version'], '1.2.0')
            self.assertEqual(pkg['package_format'], 'lib1')

    def test_resolve_package_not_found(self):
        err = urllib.error.HTTPError('https://central.example.com', 404, 'Not Found', {}, io.BytesIO(b'{"exists": false}'))
        with patch('urllib.request.urlopen', side_effect=err):
            with self.assertRaises(PackageNotFoundError):
                resolve_package('nonexistent', registry_url='https://central.example.com')

    def test_download_artifact_and_verify_checksum(self):
        content = b'BGLIB1\0\0dummy binary payload'
        content_sha = hashlib.sha256(content).hexdigest()

        mock_response = io.BytesIO(content)
        with patch('urllib.request.urlopen', return_value=mock_response):
            data = download_package_artifact(
                'https://central.example.com/download',
                expected_checksum=content_sha,
            )
            self.assertEqual(data, content)

    def test_download_artifact_integrity_failure(self):
        content = b'BGLIB1\0\0corrupted binary payload'
        mock_response = io.BytesIO(content)
        with patch('urllib.request.urlopen', return_value=mock_response):
            with self.assertRaises(IntegrityError):
                download_package_artifact(
                    'https://central.example.com/download',
                    expected_checksum='sha256:0000000000000000000000000000000000000000000000000000000000000000',
                )

    def test_install_package_to_directory(self):
        content = b'BGLIB1\0\0sample package bytes'
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
                )
                self.assertTrue(installed_file.is_file())
                self.assertEqual(installed_file.name, 'network.lib')
                self.assertEqual(installed_file.read_bytes(), content)


if __name__ == '__main__':
    unittest.main()

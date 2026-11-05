import platform as host_platform
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from core.compiler import Compiler
from core.compiler.platforms import (
    architecture_name,
    detect_host_platform,
    detect_host_system,
    normalize_architecture,
    normalize_system,
    validate_architecture_option,
    validate_system_option,
)


class PlatformTests(unittest.TestCase):
    def test_normalizes_system_aliases(self):
        self.assertEqual('windows', normalize_system('win32'))
        self.assertEqual('darwin', normalize_system('macOS'))
        self.assertEqual('linux', normalize_system('GNU/Linux'))

    def test_rejects_known_but_unsupported_system(self):
        with self.assertRaisesRegex(ValueError, 'reconocido.*no.*soportado'):
            validate_system_option('android')

    def test_detects_android_separately_from_linux(self):
        info = SimpleNamespace(system='Linux', machine='aarch64')
        with mock.patch.object(host_platform, 'uname', return_value=info), \
             mock.patch.object(host_platform, 'system', return_value='Linux'), \
             mock.patch.object(host_platform, 'platform', return_value='Linux-Android'), \
             mock.patch.object(host_platform, 'release', return_value='6.1'), \
             mock.patch.object(host_platform, 'machine', return_value='aarch64'):
            self.assertEqual('android', detect_host_system())

    def test_detects_and_normalizes_host_architecture(self):
        info = SimpleNamespace(system='Windows', machine='ARM64')
        with mock.patch.object(host_platform, 'uname', return_value=info), \
             mock.patch.object(host_platform, 'system', return_value='Windows'), \
             mock.patch.object(host_platform, 'platform', return_value='Windows-ARM64'), \
             mock.patch.object(host_platform, 'release', return_value='11'), \
             mock.patch.object(host_platform, 'machine', return_value='ARM64'), \
             mock.patch.object(host_platform, 'architecture', return_value=('64bit', '')):
            detected = detect_host_platform()

        self.assertEqual('windows', detected.system)
        self.assertEqual('aarch64', detected.architecture)
        self.assertEqual('64bit', detected.bitness)

    def test_preserves_llvm_triple_tail_when_normalizing_architecture(self):
        triple = normalize_architecture('AMD64-unknown-linux-gnu')
        self.assertEqual('x86_64-unknown-linux-gnu', triple)
        self.assertEqual('x86_64', architecture_name(triple))
        self.assertEqual(triple, validate_architecture_option(triple))

    def test_rejects_unknown_and_unsupported_architectures(self):
        with self.assertRaisesRegex(ValueError, 'valor invalido'):
            validate_architecture_option('not-an-architecture')
        with self.assertRaisesRegex(ValueError, 'reconocida.*no.*soportada'):
            validate_architecture_option('ppc64')

    def test_rejects_android_triple_until_backend_support_exists(self):
        with self.assertRaisesRegex(ValueError, 'Android.*reconocido.*no.*soportado'):
            Compiler._validate_target_configuration(
                Path('android_probe.bg'),
                'linux',
                'aarch64',
                'none',
                'aarch64-linux-android35',
            )

from __future__ import annotations

import unittest
from unittest import mock

import main
from core.version import BAGRON_VERSION


class CliVersionTests(unittest.TestCase):
    def test_help_uses_only_the_lowercase_cli_name(self):
        help_text = main._main_help()

        self.assertIn('bagron <archivo.bg>', help_text)
        self.assertIn('bagron --version', help_text)
        self.assertIn('Bagron.', help_text)
        self.assertNotIn('Bagron <archivo.bg>', help_text)
        self.assertNotIn('Bagron --vscode', help_text)

    def test_version_flag_reports_compiler_version(self):
        with mock.patch('builtins.print') as output:
            result = main.main(['--version'])

        self.assertEqual(0, result)
        output.assert_called_once_with(f'Bagron {BAGRON_VERSION}')

    def test_short_version_flag_reports_compiler_version(self):
        with mock.patch('builtins.print') as output:
            result = main.main(['-V'])

        self.assertEqual(0, result)
        output.assert_called_once_with(f'Bagron {BAGRON_VERSION}')


if __name__ == '__main__':
    unittest.main()

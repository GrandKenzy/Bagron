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
        self.assertIn('bagron library --v1 <source> -o <archivo.lib>', help_text)
        self.assertIn('bagron library --v2 <source> -o <archivo.lib>', help_text)
        self.assertIn('bagron inspect <archivo.lib>', help_text)
        self.assertIn('bagron verify <archivo.lib>', help_text)
        self.assertIn('bagron unpack <archivo.lib> <destino>', help_text)
        self.assertNotIn('vnma run main.py', help_text)
        self.assertNotIn('El frontend Gram FFI produce GIR', help_text)
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

    def test_install_module_copies_file_into_modules(self):
        import tempfile
        import os
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            work_dir = Path(td)
            src_file = work_dir / 'my_mod.bg'
            src_file.write_text('public func f() int32: return 1\n', encoding='utf-8')

            with mock.patch.dict(os.environ, {'BAGRON_CALLER_DIR': str(work_dir)}):
                ret = main.main(['install', '--module', str(src_file)])

            self.assertEqual(0, ret)
            dest_file = work_dir / 'modules' / 'my_mod.bg'
            self.assertTrue(dest_file.is_file())
            self.assertEqual(src_file.read_text(encoding='utf-8'), dest_file.read_text(encoding='utf-8'))

    def test_install_library_copies_existing_lib(self):
        import tempfile
        import os
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            work_dir = Path(td)
            src_lib = work_dir / 'sample.lib'
            src_lib.write_bytes(b'BGLIB1\0\0dummy')

            with mock.patch.dict(os.environ, {'BAGRON_CALLER_DIR': str(work_dir)}):
                ret = main.main(['install', '--library', str(src_lib)])

            self.assertEqual(0, ret)
            dest_lib = work_dir / 'libs' / 'sample.lib'
            self.assertTrue(dest_lib.is_file())
            self.assertEqual(src_lib.read_bytes(), dest_lib.read_bytes())

    def test_install_library_v1_packs_directory(self):
        import tempfile
        import os
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            work_dir = Path(td)
            lib_src = work_dir / 'MyLib'
            (lib_src / 'modules').mkdir(parents=True)
            (lib_src / 'modules' / 'helper.bg').write_text(
                'public func answer() int32:\n    return 42\n',
                encoding='utf-8',
            )

            with mock.patch.dict(os.environ, {'BAGRON_CALLER_DIR': str(work_dir)}):
                ret = main.main(['install', '--library', '--v1', str(lib_src)])

            self.assertEqual(0, ret)
            dest_lib = work_dir / 'libs' / 'MyLib.lib'
            self.assertTrue(dest_lib.is_file())


if __name__ == '__main__':
    unittest.main()

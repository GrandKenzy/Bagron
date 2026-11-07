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
        self.assertIn('bagron sign <directorio>', help_text)
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
            from core.library import pack_library
            source = work_dir / 'source'
            source.mkdir()
            (source / 'sample.bg').write_text(
                'public func answer() int32:\n    return 42\n',
                encoding='utf-8',
            )
            pack_library(source, src_lib, name='sample', version='0.1.0')

            with mock.patch.dict(os.environ, {'BAGRON_CALLER_DIR': str(work_dir)}):
                ret = main.main(['install', '--library', str(src_lib)])

            self.assertEqual(0, ret)
            dest_lib = work_dir / 'libs' / 'sample.lib'
            self.assertTrue(dest_lib.is_file())
            self.assertEqual(src_lib.read_bytes(), dest_lib.read_bytes())

    def test_install_library_rejects_name_path_traversal(self):
        import tempfile
        import os
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            work_dir = Path(td)
            src_lib = work_dir / 'sample.lib'
            source = work_dir / 'source'
            source.mkdir()
            (source / 'sample.bg').write_text(
                'public func answer() int32:\n    return 42\n',
                encoding='utf-8',
            )
            from core.library import pack_library
            pack_library(source, src_lib, name='sample', version='0.1.0')

            with mock.patch.dict(os.environ, {'BAGRON_CALLER_DIR': str(work_dir)}):
                ret = main.main([
                    'install', '--library', str(src_lib), '--name', '..\\outside',
                ])

            self.assertEqual(2, ret)
            self.assertFalse((work_dir / 'outside.lib').exists())

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
            (lib_src / 'meta.toml').write_text(
                '[package]\n'
                'name = "MyLib"\n'
                'version = "1.0.0"\n\n'
                '[author]\n'
                'name = "Tester"\n'
                'signature = ""\n',
                encoding='utf-8',
            )

            with mock.patch.dict(os.environ, {'BAGRON_CALLER_DIR': str(work_dir)}):
                ret_sign = main.main(['sign', str(lib_src)])
                ret = main.main(['install', '--library', '--v1', str(lib_src), '--version', '1.0.0'])

            self.assertEqual(0, ret_sign)
            self.assertEqual(0, ret)
            dest_lib = work_dir / 'libs' / 'MyLib.lib'
            self.assertTrue(dest_lib.is_file())

    def test_install_library_rejects_invalid_signature_without_override(self):
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
            (lib_src / 'meta.toml').write_text(
                '[package]\nname = "MyLib"\nversion = "1.0.0"\n\n'
                '[author]\nname = "Tester"\nsignature = "sha256:' + '0' * 64 + '"\n',
                encoding='utf-8',
            )

            with mock.patch.dict(os.environ, {'BAGRON_CALLER_DIR': str(work_dir)}):
                rejected = main.main(['install', '--library', '--v1', str(lib_src)])
                allowed = main.main([
                    'install', '--library', '--v1', str(lib_src),
                    '--version', '1.0.0', '--allow-unverified',
                ])

            self.assertEqual(1, rejected)
            self.assertEqual(0, allowed)
            self.assertTrue((work_dir / 'libs' / 'MyLib.lib').is_file())


    def test_library_command_resolves_relative_paths_with_caller_dir(self):
        import tempfile
        import os
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            work_dir = Path(td)
            lib_src = work_dir / 'windows'
            (lib_src / 'modules').mkdir(parents=True)
            (lib_src / 'modules' / 'helper.bg').write_text(
                'public func answer() int32:\n    return 42\n',
                encoding='utf-8',
            )

            with mock.patch.dict(os.environ, {'BAGRON_CALLER_DIR': str(work_dir)}):
                ret = main.main(['library', '--v1', 'windows', '-o', 'windowstest.lib'])

            self.assertEqual(0, ret)
            dest_lib = work_dir / 'windowstest.lib'
            self.assertTrue(dest_lib.is_file())

    def test_library_command_supports_alternative_argument_order(self):
        import tempfile
        import os
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            work_dir = Path(td)
            lib_src = work_dir / 'windows'
            (lib_src / 'modules').mkdir(parents=True)
            (lib_src / 'modules' / 'helper.bg').write_text(
                'public func answer() int32:\n    return 42\n',
                encoding='utf-8',
            )

            with mock.patch.dict(os.environ, {'BAGRON_CALLER_DIR': str(work_dir)}):
                ret = main.main(['library', 'windows', '--v1', '-o', 'windowstest2.lib'])

            self.assertEqual(0, ret)
            dest_lib = work_dir / 'windowstest2.lib'
            self.assertTrue(dest_lib.is_file())

    def test_library_inspect_verify_unpack_resolve_relative_paths(self):
        import tempfile
        import os
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            work_dir = Path(td)
            lib_src = work_dir / 'windows'
            (lib_src / 'modules').mkdir(parents=True)
            (lib_src / 'modules' / 'helper.bg').write_text(
                'public func answer() int32:\n    return 42\n',
                encoding='utf-8',
            )

            with mock.patch.dict(os.environ, {'BAGRON_CALLER_DIR': str(work_dir)}):
                ret_pack = main.main(['library', '--v1', 'windows', '-o', 'windowstest.lib'])
                self.assertEqual(0, ret_pack)

                ret_inspect = main.main(['inspect', 'windowstest.lib'])
                self.assertEqual(0, ret_inspect)

                ret_verify = main.main(['verify', 'windowstest.lib'])
                self.assertEqual(0, ret_verify)

                ret_unpack = main.main(['unpack', 'windowstest.lib', 'unpacked'])
                self.assertEqual(0, ret_unpack)
                self.assertTrue((work_dir / 'unpacked').is_dir())


    def test_sign_and_verify_cli_command(self):
        import tempfile
        import os
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            work_dir = Path(td)
            lib_src = work_dir / 'mylib'
            (lib_src / 'modules').mkdir(parents=True)
            (lib_src / 'modules' / 'code.bg').write_text(
                'public func answer() int32:\n    return 42\n',
                encoding='utf-8',
            )
            (lib_src / 'meta.toml').write_text(
                '[package]\n'
                'name = "mylib"\n'
                'version = "1.0.0"\n\n'
                '[author]\n'
                'name = "Discentra Community"\n'
                'signature = ""\n',
                encoding='utf-8',
            )

            with mock.patch.dict(os.environ, {'BAGRON_CALLER_DIR': str(work_dir)}):
                ret_sign = main.main(['sign', 'mylib'])
                self.assertEqual(0, ret_sign)

                meta_content = (lib_src / 'meta.toml').read_text(encoding='utf-8')
                self.assertIn('signature = "sha256:', meta_content)

                ret_verify = main.main(['verify', 'mylib'])
                self.assertEqual(0, ret_verify)


if __name__ == '__main__':
    unittest.main()

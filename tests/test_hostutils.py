from pathlib import Path
import tempfile
import unittest

from core.hosting import (
    bump_semver_patch,
    compute_author_signature,
    inspect_build_artifact,
    run_hostutils,
)


class TestHostUtils(unittest.TestCase):
    def test_bump_semver_patch(self):
        self.assertEqual(bump_semver_patch('1.1.4'), '1.1.5')
        self.assertEqual(bump_semver_patch('2.0.0'), '2.0.1')
        self.assertEqual(bump_semver_patch('0.1'), '0.1.1')
        self.assertEqual(bump_semver_patch('1'), '1.0.1')

    def test_compute_author_signature(self):
        sig = compute_author_signature('Author', 'mypkg', '1.0.0', 'abc123sha')
        self.assertTrue(sig.startswith('sha256:'))
        self.assertEqual(len(sig), 71)  # 'sha256:' + 64 hex chars

    def test_run_hostutils_in_temp_repo(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            build_dir = base / 'build'
            central_dir = base / 'discentra_central'
            build_dir.mkdir()
            central_dir.mkdir()

            # Create dummy build artifact
            art_file = build_dir / 'sample.lib'
            art_file.write_bytes(b'dummy content 1')

            # Create manifest.json
            manifest_json = central_dir / 'manifest.json'
            manifest_json.write_text(
                '{\n'
                '  "repository": {\n'
                '    "name": "testrepo",\n'
                '    "author": "Tester"\n'
                '  },\n'
                '  "packages": {\n'
                '    "sample": {\n'
                '      "description": "Sample test library",\n'
                '      "license": "Apache-2.0"\n'
                '    }\n'
                '  }\n'
                '}\n',
                encoding='utf-8',
            )

            # First run: new package, auto_patch=True
            ret = run_hostutils(base, auto_patch=True)
            self.assertEqual(ret, 0)

            packages_toml = (central_dir / 'packages.toml').read_text(encoding='utf-8')
            manifest_toml = (central_dir / 'manifest.toml').read_text(encoding='utf-8')

            self.assertIn('name = "sample"', packages_toml)
            self.assertIn('version = "1.0.0"', packages_toml)
            self.assertIn('description = "Sample test library"', packages_toml)
            self.assertIn('name = "sample"', manifest_toml)
            self.assertIn('sha256 = ', manifest_toml)

            # Second run: unmodified artifact -> nothing changes
            ret2 = run_hostutils(base, auto_patch=True)
            self.assertEqual(ret2, 0)
            packages_toml_2 = (central_dir / 'packages.toml').read_text(encoding='utf-8')
            self.assertEqual(packages_toml, packages_toml_2)

            # Modify artifact
            art_file.write_bytes(b'dummy content 2 (modified)')

            # Third run: modified artifact with interactive mock input
            def mock_input(prompt: str) -> str:
                return '1.2.0'

            ret3 = run_hostutils(base, input_fn=mock_input)
            self.assertEqual(ret3, 0)

            packages_toml_3 = (central_dir / 'packages.toml').read_text(encoding='utf-8')
            manifest_toml_3 = (central_dir / 'manifest.toml').read_text(encoding='utf-8')

            self.assertIn('version = "1.2.0"', packages_toml_3)
            self.assertNotEqual(manifest_toml, manifest_toml_3)


    def test_run_hostutils_dedicated_repo(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            pkg_toml = base / 'package.toml'
            pkg_toml.write_text(
                '[package]\n'
                'name = "mylib"\n'
                'version = "1.0.0"\n'
                'kind = "librería"\n'
                'format = "lib1"\n'
                'description = "Dedicated test library"\n'
                'license = "MIT"\n'
                '\n'
                '[author]\n'
                'name = "Tester"\n'
                'signature = ""\n'
                '\n'
                '[build]\n'
                'entry = "main.bg"\n'
                'modules = "modules"\n',
                encoding='utf-8',
            )

            main_file = base / 'main.bg'
            main_file.write_text(
                'func answer() int32:\n    return 42\n',
                encoding='utf-8',
            )

            modules_dir = base / 'modules'
            modules_dir.mkdir()
            sub_file = modules_dir / 'sub.bg'
            sub_file.write_text(
                'func extra() int32:\n    return 10\n',
                encoding='utf-8',
            )

            # First run: should automatically package mylib.lib and generate manifests
            ret = run_hostutils(base, auto_patch=True)
            self.assertEqual(ret, 0)

            built_lib = base / 'build' / 'mylib.lib'
            self.assertTrue(built_lib.is_file())

            central_dir = base / 'discentra_central'
            packages_toml = (central_dir / 'packages.toml').read_text(encoding='utf-8')
            manifest_toml = (central_dir / 'manifest.toml').read_text(encoding='utf-8')
            updated_pkg_toml = pkg_toml.read_text(encoding='utf-8')

            self.assertIn('name = "mylib"', packages_toml)
            self.assertIn('version = "1.0.0"', packages_toml)
            self.assertIn('file = "mylib.lib"', packages_toml)
            self.assertIn('name = "mylib"', manifest_toml)
            self.assertIn('file = "mylib.lib"', manifest_toml)
            self.assertIn('sha256:', updated_pkg_toml)

            # Second run: unchanged
            ret2 = run_hostutils(base, auto_patch=True)
            self.assertEqual(ret2, 0)
            self.assertEqual(packages_toml, (central_dir / 'packages.toml').read_text(encoding='utf-8'))

            # Modify module file and delete artifact so hostutils repacks with new source
            sub_file.write_text(
                'func extra() int32:\n    return 20\n',
                encoding='utf-8',
            )
            built_lib.unlink()

            # Run hostutils with auto-bump
            ret3 = run_hostutils(base, auto_patch=True)
            self.assertEqual(ret3, 0)

            packages_toml_3 = (central_dir / 'packages.toml').read_text(encoding='utf-8')
            manifest_toml_3 = (central_dir / 'manifest.toml').read_text(encoding='utf-8')
            updated_pkg_toml_3 = pkg_toml.read_text(encoding='utf-8')

            # Version should bump to 1.0.1
            self.assertIn('version = "1.0.1"', packages_toml_3)
            self.assertIn('version = "1.0.1"', updated_pkg_toml_3)


if __name__ == '__main__':
    unittest.main()

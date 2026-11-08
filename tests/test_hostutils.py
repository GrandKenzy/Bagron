import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.hosting import (
    HostingError,
    _atomic_write_texts,
    _pack_library_atomically,
    bump_semver_patch,
    compute_author_signature,
    inspect_build_artifact,
    run_hostutils,
)
from core.library import pack_library


class TestHostUtils(unittest.TestCase):
    def _write_lib1(
        self,
        source_root: Path,
        artifact: Path,
        *,
        name: str,
        body: str,
        version: str = '1.0.0',
    ) -> None:
        source_root.mkdir(parents=True, exist_ok=True)
        (source_root / 'main.bg').write_text(
            f'func answer() int32:\n    return {body}\n',
            encoding='utf-8',
        )
        pack_library(source_root, artifact, name=name, version=version)

    def test_bump_semver_patch(self):
        self.assertEqual(bump_semver_patch('1.1.4'), '1.1.5')
        self.assertEqual(bump_semver_patch('2.0.0'), '2.0.1')
        with self.assertRaises(HostingError):
            bump_semver_patch('0.1')
        with self.assertRaises(HostingError):
            bump_semver_patch('1')
        with self.assertRaises(HostingError):
            bump_semver_patch('1.2.x')

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

            # Create a valid lib1 build artifact.
            art_file = build_dir / 'sample.lib'
            source_dir = base / 'sample-source'
            self._write_lib1(source_dir, art_file, name='sample', body='1')

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
            self._write_lib1(source_dir, art_file, name='sample', body='2')

            # Third run: modified artifact with the short interactive prompt.
            prompts = []

            def mock_input(prompt: str) -> str:
                prompts.append(prompt)
                return ''

            ret3 = run_hostutils(base, input_fn=mock_input)
            self.assertEqual(ret3, 0)
            self.assertEqual(['set version from sample 1.0.0: '], prompts)

            packages_toml_3 = (central_dir / 'packages.toml').read_text(encoding='utf-8')
            manifest_toml_3 = (central_dir / 'manifest.toml').read_text(encoding='utf-8')

            self.assertIn('version = "1.0.1"', packages_toml_3)
            self.assertNotEqual(manifest_toml, manifest_toml_3)

            # Fourth run: invalid versions are rejected and requested again.
            self._write_lib1(source_dir, art_file, name='sample', body='3', version='1.0.1')
            values = iter(['1.2', '1.2.2'])

            def invalid_then_valid(prompt: str) -> str:
                prompts.append(prompt)
                return next(values)

            ret4 = run_hostutils(base, input_fn=invalid_then_valid)
            self.assertEqual(ret4, 0)

            packages_toml_4 = (central_dir / 'packages.toml').read_text(encoding='utf-8')
            self.assertIn('version = "1.2.2"', packages_toml_4)
            self.assertEqual(
                ['set version from sample 1.0.0: ', 'set version from sample 1.0.1: ',
                 'set version from sample 1.0.1: '],
                prompts,
            )

    def test_new_package_does_not_prompt_for_a_version(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            (base / 'build').mkdir()
            (base / 'discentra_central').mkdir()
            self._write_lib1(
                base / 'sample-source',
                base / 'build' / 'sample.lib',
                name='sample',
                body='1',
            )

            prompts = []

            def unexpected_prompt(prompt: str) -> str:
                prompts.append(prompt)
                raise AssertionError('un paquete nuevo no debe solicitar versión')

            self.assertEqual(run_hostutils(base, input_fn=unexpected_prompt), 0)
            self.assertEqual([], prompts)

    def test_set_version_requires_a_valid_semver(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            (base / 'build').mkdir()
            (base / 'discentra_central').mkdir()
            artifact = base / 'build' / 'sample.lib'
            source_dir = base / 'sample-source'
            self._write_lib1(source_dir, artifact, name='sample', body='1')
            self.assertEqual(run_hostutils(base, auto_patch=True), 0)
            self._write_lib1(source_dir, artifact, name='sample', body='2')

            with self.assertRaises(HostingError):
                run_hostutils(base, set_versions={'sample': '1.2'})

    def test_interactive_prompt_uses_explicit_version(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            (base / 'build').mkdir()
            (base / 'discentra_central').mkdir()
            artifact = base / 'build' / 'sample.lib'
            source_dir = base / 'sample-source'
            self._write_lib1(source_dir, artifact, name='sample', body='1')
            self.assertEqual(run_hostutils(base, auto_patch=True), 0)
            self._write_lib1(source_dir, artifact, name='sample', body='2')

            self.assertEqual(
                run_hostutils(base, input_fn=lambda prompt: '1.2.2'),
                0,
            )
            packages = (base / 'discentra_central' / 'packages.toml').read_text(encoding='utf-8')
            self.assertIn('version = "1.2.2"', packages)


    def test_atomic_library_packaging_preserves_existing_artifact_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            source = base / 'source'
            source.mkdir()
            destination = base / 'build' / 'sample.lib'
            destination.parent.mkdir()
            destination.write_bytes(b'previous valid artifact')

            def failing_packer(source_path, output_path, *, name, version):
                Path(output_path).write_bytes(b'partial artifact')
                raise RuntimeError('simulated pack failure')

            with self.assertRaises(RuntimeError):
                _pack_library_atomically(
                    failing_packer,
                    source,
                    destination,
                    name='sample',
                    version='1.0.0',
                )

            self.assertEqual(b'previous valid artifact', destination.read_bytes())
            self.assertEqual(
                [],
                [item for item in destination.parent.iterdir() if item.name.startswith('.sample')],
            )


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

    def test_dedicated_dry_run_does_not_create_or_modify_repository_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            pkg_toml = base / 'package.toml'
            pkg_toml.write_text(
                '[package]\n'
                'name = "drylib"\n'
                'version = "1.0.0"\n'
                'kind = "librería"\n'
                'format = "lib1"\n\n'
                '[author]\n'
                'name = "Tester"\n'
                'signature = ""\n',
                encoding='utf-8',
            )
            (base / 'main.bg').write_text(
                'public func answer() int32:\n    return 42\n',
                encoding='utf-8',
            )
            original_pkg_toml = pkg_toml.read_bytes()

            ret = run_hostutils(base, auto_patch=True, dry_run=True)

            self.assertEqual(ret, 0)
            self.assertEqual(pkg_toml.read_bytes(), original_pkg_toml)
            self.assertFalse((base / 'build').exists())
            self.assertFalse((base / 'discentra_central').exists())

    def test_manifest_updates_roll_back_when_a_replacement_fails(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            first = base / 'packages.toml'
            second = base / 'manifest.toml'
            first.write_text('old packages\n', encoding='utf-8')
            second.write_text('old manifest\n', encoding='utf-8')
            real_replace = os.replace
            calls = 0

            def fail_second_replace(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError('simulated manifest replacement failure')
                return real_replace(source, destination)

            with patch('core.hosting.os.replace', side_effect=fail_second_replace):
                with self.assertRaises(OSError):
                    _atomic_write_texts([
                        (first, 'new packages\n'),
                        (second, 'new manifest\n'),
                    ])

            self.assertEqual(first.read_text(encoding='utf-8'), 'old packages\n')
            self.assertEqual(second.read_text(encoding='utf-8'), 'old manifest\n')


if __name__ == '__main__':
    unittest.main()

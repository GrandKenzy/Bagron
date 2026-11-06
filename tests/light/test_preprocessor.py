from pathlib import Path
import tempfile
import unittest

from core.compiler.links import extract_link_directives
from core.compiler.prep import PrepError, _normalize_dialect, preprocess_conditionals


class ConditionalPreprocessorTests(unittest.TestCase):
    def _process(
        self,
        source: str,
        *,
        system: str = 'windows',
        architecture: str = 'x86_64',
    ) -> tuple[list[str], list[str]]:
        return preprocess_conditionals(
            source.splitlines(keepends=True),
            Path('fixture.bg'),
            system=system,
            architecture=architecture,
        )

    def test_only_selected_os_branch_reaches_the_parser(self):
        transformed, errors = self._process(
            '#if OS, "windows"\n'
            'func selected() int32:\n'
            '    return 1\n'
            '#else\n'
            'this is not Bagron\n'
            '#end\n'
        )

        self.assertEqual([], errors)
        self.assertEqual(
            [
                '\n',
                'func selected() int32:\n',
                '    return 1\n',
                '\n',
                '\n',
                '\n',
            ],
            transformed,
        )

    def test_elif_matches_architecture_alias(self):
        transformed, errors = self._process(
            '#if OS, "linux"\n'
            'wrong_os\n'
            '#elif ARCH, "amd"\n'
            'selected_arch\n'
            '#else\n'
            'wrong_fallback\n'
            '#end\n',
            system='windows',
            architecture='x86_64',
        )

        self.assertEqual([], errors)
        self.assertEqual(
            ['\n', '\n', '\n', 'selected_arch\n', '\n', '\n', '\n'],
            transformed,
        )

    def test_archb_matches_target_width_and_llvm_triples(self):
        source = (
            '#if ARCHB, "64"\n'
            'wide\n'
            '#elif ARCHB, "32"\n'
            'narrow\n'
            '#else\n'
            'unknown\n'
            '#end\n'
        )

        for architecture, selected in (
            ('x86_64', 'wide'),
            ('aarch64-linux-android35', 'wide'),
            ('riscv32', 'narrow'),
        ):
            with self.subTest(architecture=architecture):
                transformed, errors = self._process(
                    source,
                    architecture=architecture,
                )

                self.assertEqual([], errors)
                self.assertEqual(selected + '\n', transformed[1 if selected == 'wide' else 3])
                self.assertNotIn(
                    (('narrow' if selected == 'wide' else 'wide') + '\n'),
                    transformed,
                )

    def test_archb_rejects_noncanonical_condition_syntax(self):
        _, errors = self._process('#if ARCHB "64"\nselected\n#end\n')

        self.assertTrue(errors)
        self.assertIn('ARCHB', errors[0])

    def test_rejects_nested_conditionals_and_keeps_assembler_end(self):
        transformed, errors = self._process(
            '#if OS, "windows"\n'
            '#if ARCH, "amd"\n'
            'nested\n'
            '#end\n'
            '#end\n'
            '#assembler "intel"\n'
            '    nop\n'
            '#end\n'
        )

        self.assertIn('no se pueden anidar', '\n'.join(errors))
        self.assertEqual('#assembler "intel"\n', transformed[5])
        self.assertEqual('#end\n', transformed[7])

    def test_accepts_only_canonical_assembler_dialects(self):
        self.assertEqual('intel', _normalize_dialect('intel'))
        self.assertEqual('att', _normalize_dialect('att'))
        for alias in (
            'gas-intel', 'intel-gas', 'gas_intel', 'intel-nasm', 'at&t', 'att_syntax'
        ):
            with self.subTest(alias=alias), self.assertRaises(PrepError):
                _normalize_dialect(alias)


class LinkDirectiveTests(unittest.TestCase):
    def test_resolves_multiple_project_local_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'main.bg'
            (root / 'bins').mkdir()
            (root / 'vendor' / 'other').mkdir(parents=True)

            transformed, links, errors = extract_link_directives(
                [
                    '#link "./bins"\n',
                    'func main() int32:\n',
                    '    pass\n',
                    '#link "vendor/other/../other"\n',
                ],
                source,
                project_root=root,
                allow=True,
            )

        self.assertEqual([], errors)
        self.assertEqual(
            [(root / 'bins').resolve(), (root / 'vendor' / 'other').resolve()],
            links,
        )
        self.assertEqual(['\n', 'func main() int32:\n', '    pass\n', '\n'], transformed)

    def test_rejects_files_and_paths_outside_the_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'main.bg'
            (root / 'not_a_directory.txt').write_text('x', encoding='utf-8')
            transformed, links, errors = extract_link_directives(
                [
                    '#link "not_a_directory.txt"\n',
                    '#link "../outside"\n',
                ],
                source,
                project_root=root,
                allow=True,
            )

        self.assertEqual([], links)
        self.assertEqual(['\n', '\n'], transformed)
        self.assertIn('requiere un directorio', errors[0])
        self.assertIn('fuera del proyecto', errors[1])

    def test_imported_module_cannot_add_link_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'library.bg'
            (root / 'bins').mkdir()
            transformed, links, errors = extract_link_directives(
                ['#link "./bins"\n'],
                source,
                project_root=root,
                allow=False,
            )

        self.assertEqual([], links)
        self.assertEqual(['\n'], transformed)
        self.assertIn('solo se permite en el modulo principal', errors[0])

    def test_rejects_empty_link_path(self):
        transformed, links, errors = extract_link_directives(
            ['#link ""\n'],
            Path('main.bg'),
            project_root=Path('.'),
            allow=True,
        )

        self.assertEqual(['\n'], transformed)
        self.assertEqual([], links)
        self.assertIn('ruta de directorio no vacia', errors[0])



    def test_link_resolves_folder_from_bagron_root_libs(self):
        with tempfile.TemporaryDirectory() as fake_bagron_dir, tempfile.TemporaryDirectory() as project_dir:
            fake_bagron = Path(fake_bagron_dir)
            (fake_bagron / 'libs' / 'SDL3').mkdir(parents=True)
            root = Path(project_dir)
            source = root / 'main.bg'

            from unittest.mock import patch
            with patch('core.globvars.BAGRON_ROOT', fake_bagron):
                transformed, links, errors = extract_link_directives(
                    ['#link "SDL3"\n'],
                    source,
                    project_root=root,
                    allow=True,
                )

            self.assertEqual([], errors)
            self.assertEqual([(fake_bagron / 'libs' / 'SDL3').resolve()], links)

    def test_link_resolves_folder_from_bagron_root_modules(self):
        with tempfile.TemporaryDirectory() as fake_bagron_dir, tempfile.TemporaryDirectory() as project_dir:
            fake_bagron = Path(fake_bagron_dir)
            (fake_bagron / 'modules' / 'shared_bins').mkdir(parents=True)
            root = Path(project_dir)
            source = root / 'main.bg'

            from unittest.mock import patch
            with patch('core.globvars.BAGRON_ROOT', fake_bagron):
                transformed, links, errors = extract_link_directives(
                    ['#link "shared_bins"\n'],
                    source,
                    project_root=root,
                    allow=True,
                )

            self.assertEqual([], errors)
            self.assertEqual([(fake_bagron / 'modules' / 'shared_bins').resolve()], links)

    def test_link_prefers_local_project_over_bagron_root(self):
        with tempfile.TemporaryDirectory() as fake_bagron_dir, tempfile.TemporaryDirectory() as project_dir:
            fake_bagron = Path(fake_bagron_dir)
            (fake_bagron / 'libs' / 'bins').mkdir(parents=True)
            root = Path(project_dir)
            (root / 'bins').mkdir(parents=True)
            source = root / 'main.bg'

            from unittest.mock import patch
            with patch('core.globvars.BAGRON_ROOT', fake_bagron):
                transformed, links, errors = extract_link_directives(
                    ['#link "bins"\n'],
                    source,
                    project_root=root,
                    allow=True,
                )

            self.assertEqual([], errors)
            self.assertEqual([(root / 'bins').resolve()], links)

if __name__ == '__main__':
    unittest.main()


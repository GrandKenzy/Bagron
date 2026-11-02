from pathlib import Path
import tempfile
import unittest

from core.compiler.links import extract_link_directives
from core.compiler.prep import preprocess_conditionals


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

    def test_rejects_nested_conditionals_and_keeps_assembler_end(self):
        transformed, errors = self._process(
            '#if OS, "windows"\n'
            '#if ARCH, "amd"\n'
            'nested\n'
            '#end\n'
            '#end\n'
            '#prep assembler "intel"\n'
            '    nop\n'
            '#end\n'
        )

        self.assertIn('no se pueden anidar', '\n'.join(errors))
        self.assertEqual('#prep assembler "intel"\n', transformed[5])
        self.assertEqual('#end\n', transformed[7])


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
        self.assertEqual([root / 'bins', root / 'vendor' / 'other'], links)
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


if __name__ == '__main__':
    unittest.main()

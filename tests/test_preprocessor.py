from pathlib import Path
import unittest

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


if __name__ == '__main__':
    unittest.main()

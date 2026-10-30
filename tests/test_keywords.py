import unittest

from core.frontend.syntax.keywords import KEYWORDS, KEYWORDS_BY_GROUP
from core.globvars import CLAUSES


class KeywordRegistryTests(unittest.TestCase):
    def test_removed_keywords_are_not_registered(self):
        registered = set(KEYWORDS)
        for words in KEYWORDS_BY_GROUP.values():
            registered.update(words)

        removed = {
            'include',
            'link',
            'object',
            'TypeAlias',
            '__instfron__',
            '__fref__',
            'macro',
            'sizeof',
            'Visibility',
        }

        self.assertTrue(removed.isdisjoint(registered))

    def test_privacy_clause_and_assembler_keywords_remain_available(self):
        registered = set(KEYWORDS)
        for words in KEYWORDS_BY_GROUP.values():
            registered.update(words)

        self.assertIn('Privacy', CLAUSES)
        self.assertIn('asm', registered)
        self.assertIn('prep', registered)


if __name__ == '__main__':
    unittest.main()

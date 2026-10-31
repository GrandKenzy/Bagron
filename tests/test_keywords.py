import unittest

from core.frontend.syntax.keywords import KEYWORDS, KEYWORDS_BY_GROUP
from core.frontend.syntax import BAGRON_SESSION
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

    def test_bagron_lexicon_is_owned_by_its_gram_session(self):
        self.assertIn('func', BAGRON_SESSION.keywords)
        self.assertTrue(BAGRON_SESSION.get_group('types').contains('int32'))
        self.assertEqual(
            BAGRON_SESSION.get_config('LEXER_COMMENT_TOKEN'),
            ';',
        )
        self.assertNotIn('**', BAGRON_SESSION.symbols)


if __name__ == '__main__':
    unittest.main()

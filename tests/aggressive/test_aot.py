"""Validación obligatoria del frontend Gram FFI que produce GIR."""

from __future__ import annotations

import unittest

from core.frontend import BAGRON_SESSION
from core.frontend.aot import AotInMemoryParser, AotParser, AotParserError


class AotFrontendTests(unittest.TestCase):
    """El parser AOT alimenta el mismo frontend semántico de Bagron."""

    @classmethod
    def setUpClass(cls):
        cls.parser = AotParser.from_config()

    def test_rejects_invalid_source(self):
        source = 'func main() int32\n    return 0\n'
        with self.assertRaises(AotParserError) as context:
            self.parser.parse(
                source,
                session=BAGRON_SESSION,
                name='invalid_aot.bg',
            )
        self.assertEqual(context.exception.status, 6)
        self.assertEqual(context.exception.line, 2)
        self.assertEqual(context.exception.column, 0)

    def test_gate_uses_in_memory_gram_driver(self):
        self.assertIsInstance(self.parser, AotInMemoryParser)
        self.assertIsNotNone(self.parser.library)
        self.assertIsNotNone(self.parser.expected_grammar_id)



if __name__ == '__main__':
    unittest.main()


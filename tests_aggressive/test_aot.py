"""Validación opt-in del frontend Gram AOT que produce GIR."""

from __future__ import annotations

import unittest
from pathlib import Path

from core.compiler import Compiler
from core.frontend import BAGRON_SESSION
from core.frontend.aot import AotParser, AotParserError


class AotFrontendTests(unittest.TestCase):
    """El parser AOT alimenta el mismo frontend semántico de Bagron."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.parser = AotParser.from_config()
        except AotParserError as error:
            raise unittest.SkipTest(
                f'Parser AOT no construido; ejecuta tools/build_aot_parser.py: {error}'
            ) from error

    def test_rejects_invalid_source(self):
        source = 'func main() int32\n    return 0\n'
        with self.assertRaises(AotParserError):
            self.parser.parse(
                source,
                session=BAGRON_SESSION,
                name='invalid_aot.bg',
            )

    def test_compiles_canon_through_gir_and_existing_backend(self):
        output = Compiler(
            aot=True,
            aot_parser=self.parser.executable,
            aot_strict=True,
        ).compile(
            Path('examples/canon/_main.bg'),
            executable=False,
        )
        self.assertTrue(Path(output).is_file())


if __name__ == '__main__':
    unittest.main()

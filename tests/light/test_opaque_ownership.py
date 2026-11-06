from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler

_OPAQUE = 'opaque FD: int32\n'
_CLOSE = _OPAQUE + 'func close_file(handle: FD) void:\n    return\n'
_CONSUME = _OPAQUE + '@consume\nfunc shut(handle: FD) void:\n    return\n'


class OpaqueOwnershipTests(unittest.TestCase):
    """Static ownership of opaque descriptors: moves, consumption and loops."""

    def _compile(self, source: str) -> Compiler:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        compiler = Compiler()
        compiler.compile(path, executable=False)
        return compiler

    def _rejects(self, source: str, pattern: str) -> None:
        with self.assertRaisesRegex(CompilationError, pattern):
            self._compile(source)

    # Transferencia de propiedad al copiar o asignar
    def test_copy_moves_ownership(self):
        self._compile(
            _CLOSE
            + 'func main() int32:\n    h: FD\n    g: FD = h\n'
            '    close_file(g)\n    return 0\n'
        )
        self._rejects(
            _CLOSE
            + 'func main() int32:\n    h: FD\n    g: FD = h\n'
            '    close_file(h)\n    return 0\n',
            'descriptor h esta moved',
        )

    def test_assignment_moves_ownership(self):
        self._compile(
            _CLOSE
            + 'func main() int32:\n    h: FD\n    g: FD\n    g = h\n'
            '    close_file(g)\n    return 0\n'
        )
        self._rejects(
            _CLOSE
            + 'func main() int32:\n    h: FD\n    g: FD\n    g = h\n'
            '    close_file(h)\n    return 0\n',
            'descriptor h esta moved',
        )

    def test_borrowed_descriptor_cannot_be_copied(self):
        self._rejects(
            _OPAQUE
            + 'func f(p: FD) void:\n    g: FD = p\n    return\n'
            'func main() int32:\n    return 0\n',
            'borrowed; no puede transferirse',
        )

    # Marcador explicito @consume
    def test_consume_decorator_closes_once(self):
        self._compile(
            _CONSUME + 'func main() int32:\n    h: FD\n    shut(h)\n    return 0\n'
        )
        self._rejects(
            _CONSUME
            + 'func main() int32:\n    h: FD\n    shut(h)\n    shut(h)\n'
            '    return 0\n',
            'descriptor h esta closed',
        )

    def test_consume_parameter_is_owned_and_can_be_forwarded(self):
        self._compile(
            _CONSUME
            + '@consume\nfunc wrap(handle: FD) void:\n    shut(handle)\n'
            '    return\n'
            'func main() int32:\n    h: FD\n    wrap(h)\n    return 0\n'
        )
        self._rejects(
            _CONSUME
            + 'func wrap(handle: FD) void:\n    shut(handle)\n    return\n'
            'func main() int32:\n    return 0\n',
            'requiere un descriptor owned',
        )

    def test_consume_requires_an_opaque_parameter(self):
        self._rejects(
            '@consume\nfunc f(x: int32) void:\n    return\n'
            'func main() int32:\n    return 0\n',
            '@consume en f requiere',
        )

    def test_ordinary_function_borrows(self):
        self._compile(
            _CLOSE
            + 'func peek(handle: FD) void:\n    return\n'
            'func main() int32:\n    h: FD\n    peek(h)\n    peek(h)\n'
            '    close_file(h)\n    return 0\n'
        )

    def test_legacy_close_prefix_warns_but_still_consumes(self):
        compiler = self._compile(
            _CLOSE + 'func main() int32:\n    return 0\n'
        )
        self.assertTrue(
            any('@consume' in warning for warning in compiler.warnings)
        )
        self._rejects(
            _CLOSE
            + 'func main() int32:\n    h: FD\n    close_file(h)\n'
            '    close_file(h)\n    return 0\n',
            'descriptor h esta closed',
        )
        compiler = self._compile(
            _CONSUME + 'func main() int32:\n    return 0\n'
        )
        self.assertEqual([], compiler.warnings)

    # Bucles
    def test_consuming_an_outer_descriptor_in_a_loop_is_rejected(self):
        self._rejects(
            _CONSUME
            + 'func main() int32:\n    h: FD\n    i: int32 = 0\n'
            '    while i < 3:\n        shut(h)\n        i = i + 1\n'
            '    return 0\n',
            'se cierra o transfiere dentro de un bucle',
        )

    def test_descriptor_local_to_the_loop_may_be_consumed(self):
        self._compile(
            _CONSUME
            + 'func main() int32:\n    i: int32 = 0\n'
            '    while i < 3:\n        h: FD\n        shut(h)\n'
            '        i = i + 1\n    return 0\n'
        )


if __name__ == '__main__':
    unittest.main()

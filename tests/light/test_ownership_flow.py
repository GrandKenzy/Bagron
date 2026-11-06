from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler

_OPAQUE = (
    'opaque FD: int32\n'
    '@consume\nfunc shut(handle: FD) void:\n    return\n'
)


class OwnershipFlowTests(unittest.TestCase):
    """Terminating branches, ``maybe_*`` states and leak detection."""

    def _compile(self, source: str, *, strict: bool = False) -> Compiler:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        compiler = Compiler()
        compiler.strict_ownership = strict
        compiler.compile(path, executable=False)
        return compiler

    def _leaks(self, compiler: Compiler) -> list[str]:
        return [w for w in compiler.warnings if 'fuga' in w]

    # Flujo terminante
    def test_branch_that_returns_does_not_poison_the_fall_through(self):
        compiler = self._compile(
            'func main() int32:\n    a: buffer[4] = 0\n    c: int32 = 1\n'
            '    if c == 1:\n        Del a\n        return 1\n'
            '    a[0] = 1\n    Del a\n    return 0\n'
        )
        self.assertEqual([], self._leaks(compiler))

    def test_branch_that_continues_does_not_poison_the_loop_exit(self):
        self._compile(
            'func main() int32:\n    a: buffer[4] = 0\n    i: int32 = 0\n'
            '    while i < 3:\n        i = i + 1\n        if i == 1:\n'
            '            continue\n    Del a\n    return 0\n'
        )

    # Estados maybe_*
    def test_conditional_del_leaves_buffer_maybe_dead(self):
        with self.assertRaisesRegex(CompilationError, 'puede estar dead'):
            self._compile(
                'func main() int32:\n    a: buffer[4] = 0\n    c: int32 = 1\n'
                '    if c == 1:\n        Del a\n    a[0] = 1\n    return 0\n'
            )

    def test_conditional_del_cannot_be_repeated(self):
        with self.assertRaisesRegex(CompilationError, 'puede estar dead'):
            self._compile(
                'func main() int32:\n    a: buffer[4] = 0\n    c: int32 = 1\n'
                '    if c == 1:\n        Del a\n    Del a\n    return 0\n'
            )

    def test_conditional_close_leaves_descriptor_maybe_closed(self):
        with self.assertRaisesRegex(CompilationError, 'puede estar closed'):
            self._compile(
                _OPAQUE
                + 'func main() int32:\n    h: FD\n    c: int32 = 1\n'
                '    if c == 1:\n        shut(h)\n    shut(h)\n    return 0\n'
            )

    def test_both_branches_consuming_is_plain_dead(self):
        compiler = self._compile(
            'func main() int32:\n    a: buffer[4] = 0\n    c: int32 = 1\n'
            '    if c == 1:\n        Del a\n    else:\n        Del a\n'
            '    return 0\n'
        )
        self.assertEqual([], self._leaks(compiler))

    # Fugas
    def test_unfreed_buffer_warns(self):
        compiler = self._compile(
            'func main() int32:\n    a: buffer[4] = 0\n    return 0\n'
        )
        self.assertEqual(1, len(self._leaks(compiler)))
        self.assertIn('buffer a', self._leaks(compiler)[0])

    def test_freed_buffer_does_not_warn(self):
        compiler = self._compile(
            'func main() int32:\n    a: buffer[4] = 0\n    Del a\n'
            '    return 0\n'
        )
        self.assertEqual([], self._leaks(compiler))

    def test_early_return_leak_is_reported_once(self):
        compiler = self._compile(
            'func main() int32:\n    a: buffer[4] = 0\n    c: int32 = 1\n'
            '    if c == 1:\n        return 1\n    Del a\n    return 0\n'
        )
        leaks = self._leaks(compiler)
        self.assertEqual(1, len(leaks))
        self.assertIn('buffer a', leaks[0])

    def test_conditional_free_reports_a_possible_leak(self):
        compiler = self._compile(
            'func main() int32:\n    a: buffer[4] = 0\n    c: int32 = 1\n'
            '    if c == 1:\n        Del a\n    return 0\n'
        )
        self.assertTrue(any('en alguna ruta' in w for w in compiler.warnings))

    def test_unclosed_descriptor_warns(self):
        compiler = self._compile(
            _OPAQUE + 'func main() int32:\n    h: FD\n    return 0\n'
        )
        self.assertEqual(1, len(self._leaks(compiler)))
        self.assertIn('descriptor h', self._leaks(compiler)[0])

    def test_moved_descriptor_does_not_leak(self):
        compiler = self._compile(
            _OPAQUE
            + 'func main() int32:\n    h: FD\n    g: FD = h\n    shut(g)\n'
            '    return 0\n'
        )
        self.assertEqual([], self._leaks(compiler))

    def test_buffer_declared_in_a_loop_body_leaks_each_iteration(self):
        compiler = self._compile(
            'func main() int32:\n    i: int32 = 0\n    while i < 2:\n'
            '        b: buffer[2] = 0\n        i = i + 1\n    return 0\n'
        )
        self.assertEqual(1, len(self._leaks(compiler)))

    def test_borrowed_parameters_do_not_leak(self):
        compiler = self._compile(
            'func peek(data: buffer[], length: Len_t) void:\n    return\n'
            'func main() int32:\n    return 0\n'
        )
        self.assertEqual([], self._leaks(compiler))

    def test_strict_ownership_turns_leaks_into_errors(self):
        source = 'func main() int32:\n    a: buffer[4] = 0\n    return 0\n'
        with self.assertRaisesRegex(CompilationError, 'fuga de memoria'):
            self._compile(source, strict=True)

    # Reconstruccion en ramas y retornos de recursos
    def test_buffer_reconstructed_in_branch_remains_owned(self):
        compiler = self._compile(
            'func main() int32:\n    a: buffer[4] = 0\n    c: int32 = 1\n'
            '    if c == 1:\n        Del a\n        a = {1, 2, 3, 4}\n'
            '    a[0] = 7\n    Del a\n    return 0\n'
        )
        self.assertEqual([], self._leaks(compiler))

    def test_overwriting_live_buffer_without_del_is_rejected(self):
        with self.assertRaisesRegex(
            CompilationError, 'requiere que el buffer este dead'
        ):
            self._compile(
                'func main() int32:\n    a: buffer[4] = 0\n'
                '    a = {1, 2, 3, 4}\n    Del a\n    return 0\n'
            )

    def test_returned_owned_descriptor_does_not_leak(self):
        compiler = self._compile(
            _OPAQUE
            + 'func make() FD:\n    h: FD\n    return h\n'
            'func main() int32:\n    h: FD = make()\n    shut(h)\n'
            '    return 0\n'
        )
        self.assertEqual([], self._leaks(compiler))

    def test_returning_borrowed_descriptor_is_rejected(self):
        with self.assertRaisesRegex(
            CompilationError, 'return requiere un descriptor owned'
        ):
            self._compile(
                _OPAQUE
                + 'func relay(p: FD) FD:\n    return p\n'
                'func main() int32:\n    return 0\n'
            )


if __name__ == '__main__':
    unittest.main()

import unittest
from test.helpers import compile_snippet


class TestClauses(unittest.TestCase):
    def test_default_clauses(self):
        storage = compile_snippet("")
        self.assertEqual(storage.arch, 'auto')
        self.assertEqual(storage.system, 'auto')
        self.assertEqual(storage.privacy, 'public')
        self.assertEqual(storage.stacklimit, -1)

    def test_arch_clause(self):
        storage = compile_snippet("clause Arch 'x86_64'\n")
        self.assertEqual(storage.arch, 'x86_64')

    def test_system_clause(self):
        storage = compile_snippet("clause System 'windows'\n")
        self.assertEqual(storage.system, 'windows')

    def test_visibility_clause(self):
        storage = compile_snippet("clause Visibility 'private'\n")
        self.assertEqual(storage.privacy, 'private')

    def test_stacklimit_clause(self):
        storage = compile_snippet("clause StackLimit 4096\n")
        self.assertEqual(storage.stacklimit, 4096)

    def test_multiple_clauses(self):
        code = (
            "clause Arch 'arm64'\n"
            "clause System 'linux'\n"
            "clause Visibility 'private'\n"
            "clause StackLimit 8192\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.arch, 'arm64')
        self.assertEqual(storage.system, 'linux')
        self.assertEqual(storage.privacy, 'private')
        self.assertEqual(storage.stacklimit, 8192)


if __name__ == '__main__':
    unittest.main()

import unittest
from test.helpers import compile_snippet


class TestEnumDecl(unittest.TestCase):
    def test_auto_increment_values(self):
        code = (
            "enum Color:\n"
            "    RED\n"
            "    GREEN\n"
            "    BLUE\n"
        )
        storage = compile_snippet(code)
        self.assertIn('Color', storage.enums)
        color = storage.enums['Color']
        self.assertEqual(color.members['RED'], 0)
        self.assertEqual(color.members['GREEN'], 1)
        self.assertEqual(color.members['BLUE'], 2)

    def test_explicit_values(self):
        code = (
            "enum Status:\n"
            "    OK = 200\n"
            "    NOT_FOUND = 404\n"
            "    ERROR = 500\n"
        )
        storage = compile_snippet(code)
        status = storage.enums['Status']
        self.assertEqual(status.members['OK'], 200)
        self.assertEqual(status.members['NOT_FOUND'], 404)
        self.assertEqual(status.members['ERROR'], 500)

    def test_mixed_explicit_and_auto_values(self):
        code = (
            "enum Step:\n"
            "    FIRST = 10\n"
            "    SECOND\n"
            "    THIRD = 25\n"
            "    FOURTH\n"
        )
        storage = compile_snippet(code)
        step = storage.enums['Step']
        self.assertEqual(step.members['FIRST'], 10)
        self.assertEqual(step.members['SECOND'], 11)
        self.assertEqual(step.members['THIRD'], 25)
        self.assertEqual(step.members['FOURTH'], 26)

    def test_negative_values(self):
        code = (
            "enum Code:\n"
            "    FAIL = -1\n"
            "    SUCCESS = 0\n"
        )
        storage = compile_snippet(code)
        code_enum = storage.enums['Code']
        self.assertEqual(code_enum.members['FAIL'], -1)
        self.assertEqual(code_enum.members['SUCCESS'], 0)

    def test_string_values(self):
        code = (
            "enum Mode:\n"
            "    FAST = 'fast'\n"
            "    SLOW = 'slow'\n"
        )
        storage = compile_snippet(code)
        mode = storage.enums['Mode']
        self.assertEqual(mode.members['FAST'], 'fast')
        self.assertEqual(mode.members['SLOW'], 'slow')

    def test_privacy_modifiers(self):
        code = (
            "private enum Secret:\n"
            "    KEY\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.enums['Secret'].privacy, 'private')

    def test_privacy_inherited_from_storage(self):
        code = (
            "clause Visibility 'private'\n"
            "enum Local:\n"
            "    A\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.enums['Local'].privacy, 'private')

    def test_empty_enum_with_pass(self):
        code = (
            "enum Empty:\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        self.assertIn('Empty', storage.enums)
        self.assertEqual(len(storage.enums['Empty'].members), 0)

    def test_collision_with_existing_variable(self):
        code = (
            "Color: int = 10\n"
            "enum Color:\n"
            "    RED\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_collision_between_enums(self):
        code = (
            "enum Color:\n"
            "    RED\n"
            "enum Color:\n"
            "    BLUE\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)


if __name__ == '__main__':
    unittest.main()

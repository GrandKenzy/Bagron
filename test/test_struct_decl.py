import unittest
from test.helpers import compile_snippet


class TestStructDecl(unittest.TestCase):
    def test_basic_struct(self):
        code = (
            "struct Point:\n"
            "    x: int\n"
            "    y: int\n"
        )
        storage = compile_snippet(code)
        self.assertIn('Point', storage.structs)
        point = storage.structs['Point']
        self.assertEqual(len(point.fields), 2)
        self.assertEqual(point.fields[0].name, 'x')
        self.assertEqual(point.fields[0].type, 'int')
        self.assertEqual(point.fields[1].name, 'y')
        self.assertEqual(point.fields[1].type, 'int')

    def test_struct_with_array_and_chain_types(self):
        code = (
            "struct User:\n"
            "    name: chain\n"
            "    age: int\n"
            "    scores: array[int, 10]\n"
        )
        storage = compile_snippet(code)
        user = storage.structs['User']
        self.assertEqual(user.field_map['name'].type, 'chain')
        self.assertEqual(user.field_map['age'].type, 'int')
        self.assertEqual(user.field_map['scores'].type, 'array[int]')


    def test_packed_struct(self):
        code = (
            "struct Packet:\n"
            "    __packed__\n"
            "    id: int\n"
        )
        storage = compile_snippet(code)
        self.assertTrue(storage.structs['Packet'].is_packed)

    def test_volatile_struct(self):
        code = (
            "__volatile__ struct HardwareReg:\n"
            "    control: int\n"
        )
        storage = compile_snippet(code)
        self.assertTrue(storage.structs['HardwareReg'].is_volatile)

    def test_aligned_struct(self):
        code = (
            "struct AlignedBuffer:\n"
            "    __align__ 16\n"
            "    data: int\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.structs['AlignedBuffer'].align, 16)

    def test_bitfield_struct(self):
        code = (
            "struct HeaderFlags:\n"
            "    int is_valid : 1\n"
            "    int priority : 3\n"
            "    int : 4\n"
        )
        storage = compile_snippet(code)
        flags = storage.structs['HeaderFlags']
        self.assertEqual(len(flags.fields), 3)
        self.assertEqual(flags.fields[0].name, 'is_valid')
        self.assertEqual(flags.fields[0].bits, 1)
        self.assertEqual(flags.fields[1].name, 'priority')
        self.assertEqual(flags.fields[1].bits, 3)
        # campo anónimo de relleno
        self.assertEqual(flags.fields[2].name, '')
        self.assertEqual(flags.fields[2].bits, 4)

    def test_privacy_modifiers(self):
        code = (
            "private struct InternalState:\n"
            "    state: int\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.structs['InternalState'].privacy, 'private')

    def test_privacy_inherited_from_storage(self):
        code = (
            "clause Visibility 'private'\n"
            "struct Config:\n"
            "    timeout: int\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.structs['Config'].privacy, 'private')

    def test_empty_struct_with_pass(self):
        code = (
            "struct Empty:\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        self.assertIn('Empty', storage.structs)
        self.assertEqual(len(storage.structs['Empty'].fields), 0)

    def test_duplicate_field_name_error(self):
        code = (
            "struct Node:\n"
            "    val: int\n"
            "    val: int\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_struct_name_collision_with_existing_variable(self):
        code = (
            "Point: int = 10\n"
            "struct Point:\n"
            "    x: int\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_struct_name_collision_with_another_struct(self):
        code = (
            "struct Vector:\n"
            "    x: int\n"
            "struct Vector:\n"
            "    y: int\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)


if __name__ == '__main__':
    unittest.main()

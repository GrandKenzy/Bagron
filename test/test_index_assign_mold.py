import unittest
from test.helpers import compile_snippet
from core.processor.objects.assign import Assign
from core.processor.objects.expression import IndexAccess
from core.processor.objects.member_access import MemberAccess


class TestIndexAccessAndComplexAssign(unittest.TestCase):
    # ==========================================
    # 1. INDEX_ACCESS Tests
    # ==========================================
    def test_array_index_access_expression(self):
        code = (
            "arr: array[int, 5]\n"
            "x: int = arr[0]\n"
        )
        storage = compile_snippet(code)
        self.assertIn('x', storage.variables)
        self.assertEqual(storage.variables['x'].type, 'int')

    def test_string_index_access_yields_char(self):
        code = (
            "s: chain = \"hello\"\n"
            "c: char = s[0]\n"
        )

        storage = compile_snippet(code)
        self.assertIn('c', storage.variables)
        self.assertEqual(storage.variables['c'].type, 'char')

    def test_pointer_index_access_yields_any(self):
        code = (
            "ptr p\n"
            "val: any = p[0]\n"
        )
        storage = compile_snippet(code)
        self.assertIn('val', storage.variables)

    def test_index_with_variable_expression(self):
        code = (
            "arr: array[int, 10]\n"
            "i: int = 3\n"
            "item: int = arr[i]\n"
        )
        storage = compile_snippet(code)
        self.assertIn('item', storage.variables)
        self.assertEqual(storage.variables['item'].type, 'int')

    def test_non_integer_index_raises_type_error(self):
        code = (
            "arr: array[int, 5]\n"
            "x: int = arr[\"hola\"]\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_float_index_raises_type_error(self):
        code = (
            "arr: array[int, 5]\n"
            "x: int = arr[1.5]\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_indexing_non_indexable_type_raises_type_error(self):
        code = (
            "a: int = 10\n"
            "b: int = a[0]\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_indexing_undeclared_variable_raises_runtime_error(self):
        code = (
            "x: int = nonexistent[0]\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_double_indexing_string_raises_type_error(self):
        code = (
            "s: chain = \"hola\"\n"
            "x: int = s[0][0]\n"
        )

        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_standalone_index_access_expression(self):
        code = (
            "arr: array[int, 5]\n"
            "x: int = arr[0]\n"
            "y: int = x\n"
        )
        storage = compile_snippet(code)
        self.assertIn('x', storage.variables)
        self.assertIn('y', storage.variables)

    # ==========================================
    # 2. Complex Assignments (VAR_ASSIGNATION)
    # ==========================================
    def test_array_element_assignment(self):
        code = (
            "arr: array[int, 5]\n"
            "arr[0] = 42\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.variables['arr'].uses, 1)

    def test_array_element_assignment_type_mismatch(self):
        code = (
            "arr: array[int, 5]\n"
            "arr[0] = \"texto\"\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_constant_array_element_assignment_raises_error(self):
        code = (
            "ARR: array[int, 5]\n"
            "ARR[0] = 10\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_struct_member_assignment(self):
        code = (
            "struct Point:\n"
            "    x: int\n"
            "    y: int\n"
            "p: Point\n"
            "p.x = 10\n"
            "p.y = 20\n"
        )
        storage = compile_snippet(code)
        self.assertIn('p', storage.variables)
        self.assertEqual(storage.variables['p'].uses, 2)

    def test_struct_member_compound_assignment(self):
        code = (
            "struct Counter:\n"
            "    count: int\n"
            "c: Counter\n"
            "c.count += 5\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.variables['c'].uses, 1)

    def test_struct_member_assignment_type_mismatch(self):
        code = (
            "struct Point:\n"
            "    x: int\n"
            "p: Point\n"
            "p.x = \"texto\"\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_struct_member_assignment_nonexistent_field(self):
        code = (
            "struct Point:\n"
            "    x: int\n"
            "p: Point\n"
            "p.z = 10\n"
        )
        with self.assertRaises(AttributeError):
            compile_snippet(code)

    def test_member_assignment_on_non_struct_raises_type_error(self):
        code = (
            "a: int = 10\n"
            "a.x = 5\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_constant_struct_member_assignment_raises_error(self):
        code = (
            "struct Point:\n"
            "    x: int\n"
            "P: Point\n"
            "P.x = 10\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_nested_struct_member_assignment(self):
        code = (
            "struct Inner:\n"
            "    val: int\n"
            "struct Outer:\n"
            "    inner: Inner\n"
            "o: Outer\n"
            "o.inner.val = 99\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.variables['o'].uses, 1)

    def test_struct_with_array_field_indexing_and_assignment(self):
        code = (
            "struct Buffer:\n"
            "    data: array[int, 10]\n"
            "b: Buffer\n"
            "b.data[0] = 123\n"
            "first: int = b.data[0]\n"
        )
        storage = compile_snippet(code)
        self.assertIn('first', storage.variables)
        self.assertEqual(storage.variables['first'].type, 'int')


class TestMoldAndFlags(unittest.TestCase):
    # ==========================================
    # 3. MOLD and FLAGS Tests
    # ==========================================
    def test_basic_mold_declaration(self):
        code = (
            "mold Person:\n"
            "    name: chain\n"
            "    age: int\n"
        )
        storage = compile_snippet(code)
        self.assertIn('Person', storage.structs)
        self.assertIn('Person', storage.molds)
        mold_obj = storage.molds['Person']
        self.assertEqual(mold_obj.kind, 'mold')
        self.assertEqual(len(mold_obj.fields), 2)
        self.assertEqual(mold_obj.field_map['name'].type, 'chain')
        self.assertEqual(mold_obj.field_map['age'].type, 'int')


    def test_mold_with_packed_and_align(self):
        code = (
            "mold AlignedData:\n"
            "    __packed__\n"
            "    __align__ 16\n"
            "    value: int\n"
        )
        storage = compile_snippet(code)
        mold_obj = storage.molds['AlignedData']
        self.assertTrue(mold_obj.is_packed)
        self.assertEqual(mold_obj.align, 16)

    def test_mold_variable_declaration_and_member_assignment(self):
        code = (
            "mold Config:\n"
            "    timeout: int\n"
            "cfg: Config\n"
            "cfg.timeout = 5000\n"
        )
        storage = compile_snippet(code)
        self.assertIn('cfg', storage.variables)
        self.assertEqual(storage.variables['cfg'].type, 'Config')
        self.assertEqual(storage.variables['cfg'].uses, 1)

    def test_basic_flags_declaration(self):
        code = (
            "flags StatusFlags:\n"
            "    int is_ready : 1\n"
            "    int has_error : 1\n"
            "    int : 6\n"
        )
        storage = compile_snippet(code)
        self.assertIn('StatusFlags', storage.structs)
        self.assertIn('StatusFlags', storage.flags)
        flags_obj = storage.flags['StatusFlags']
        self.assertEqual(flags_obj.kind, 'flags')
        self.assertEqual(len(flags_obj.fields), 3)
        self.assertEqual(flags_obj.field_map['is_ready'].bits, 1)
        self.assertEqual(flags_obj.field_map['has_error'].bits, 1)

    def test_flags_variable_declaration_and_member_assignment(self):
        code = (
            "flags CPUFlags:\n"
            "    int carry : 1\n"
            "    int zero : 1\n"
            "cpu: CPUFlags\n"
            "cpu.zero = 1\n"
        )
        storage = compile_snippet(code)
        self.assertIn('cpu', storage.variables)
        self.assertEqual(storage.variables['cpu'].type, 'CPUFlags')
        self.assertEqual(storage.variables['cpu'].uses, 1)

    def test_mold_duplicate_field_raises_error(self):
        code = (
            "mold BadMold:\n"
            "    x: int\n"
            "    x: int\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_flags_duplicate_field_raises_error(self):
        code = (
            "flags BadFlags:\n"
            "    int bit : 1\n"
            "    int bit : 1\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_mold_inside_function_scope(self):
        code = (
            "mold Vector:\n"
            "    x: int\n"
            "    y: int\n"
            "\n"
            "void do_work(a: int):\n"
            "    v: Vector\n"
            "    v.x = 10\n"
            "    v.y = 20\n"
        )
        storage = compile_snippet(code)
        self.assertIn('do_work', storage.functions)
        func = storage.functions['do_work']
        self.assertIn('v', func.scope.variables)


if __name__ == '__main__':
    unittest.main()

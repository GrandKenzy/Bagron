import unittest
from test.helpers import compile_snippet


class TestVarDecl(unittest.TestCase):
    def test_primitive_declarations(self):
        code = (
            "a: int = 10\n"
            "f: float = 3.14\n"
            "b: bool = true\n"
            "s: chain = 'hola'\n"
            "c: char = 'x'\n"
            "by: byte = 255\n"
            "m: middle = 1.5\n"
        )
        storage = compile_snippet(code)
        self.assertIn('a', storage.variables)
        self.assertEqual(storage.variables['a'].type, 'int')
        self.assertIn('f', storage.variables)
        self.assertEqual(storage.variables['f'].type, 'float')
        self.assertIn('b', storage.variables)
        self.assertEqual(storage.variables['b'].type, 'bool')
        self.assertIn('s', storage.variables)
        self.assertEqual(storage.variables['s'].type, 'chain')
        self.assertIn('c', storage.variables)
        self.assertEqual(storage.variables['c'].type, 'char')
        self.assertIn('by', storage.variables)
        self.assertEqual(storage.variables['by'].type, 'byte')
        self.assertIn('m', storage.variables)
        self.assertEqual(storage.variables['m'].type, 'middle')

    def test_partial_declaration(self):
        storage = compile_snippet("count: int\n")
        self.assertIn('count', storage.variables)
        self.assertEqual(storage.variables['count'].type, 'int')
        self.assertIsNone(storage.variables['count'].value)

    def test_privacy_modifiers(self):
        code = (
            "public a: int = 1\n"
            "private b: int = 2\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.variables['a'].privacy, 'public')
        self.assertEqual(storage.variables['b'].privacy, 'private')

    def test_privacy_default_inherited_from_storage(self):
        code = (
            "clause Visibility 'private'\n"
            "x: int = 42\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.variables['x'].privacy, 'private')

    def test_type_mismatch_int_with_str(self):
        with self.assertRaises(TypeError):
            compile_snippet("a: int = 'error'\n")

    def test_type_mismatch_bool_with_int(self):
        with self.assertRaises(TypeError):
            compile_snippet("b: bool = 100\n")

    def test_undefined_variable_in_init(self):
        with self.assertRaises(RuntimeError):
            compile_snippet("a: int = no_existe\n")

    def test_assign_variable_to_variable(self):
        code = (
            "a: int = 10\n"
            "b: int = a\n"
        )
        storage = compile_snippet(code)
        self.assertIn('b', storage.variables)
        self.assertEqual(storage.variables['b'].type, 'int')

    def test_redeclaration_collision(self):
        code = (
            "a: int = 10\n"
            "a: int = 20\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_constant_detection(self):
        code = "MAX_SIZE: int = 1024\n"
        storage = compile_snippet(code)
        self.assertTrue(storage.variables['MAX_SIZE'].is_constant)

    # =========================================================================
    # ASG-04: Declaración múltiple con tipo explícito (ej: a, b: int = x, y)
    # =========================================================================
    def test_multi_var_declaration_basic(self):
        code = "a, b: int = 10, 20\n"
        storage = compile_snippet(code)
        self.assertIn('a', storage.variables)
        self.assertIn('b', storage.variables)
        self.assertEqual(storage.variables['a'].type, 'int')
        self.assertEqual(storage.variables['b'].type, 'int')

    def test_multi_var_declaration_from_variables(self):
        code = (
            "x: int = 5\n"
            "y: int = 6\n"
            "a, b: int = x, y\n"
        )
        storage = compile_snippet(code)
        self.assertIn('a', storage.variables)
        self.assertIn('b', storage.variables)
        self.assertEqual(storage.variables['a'].type, 'int')
        self.assertEqual(storage.variables['b'].type, 'int')

    def test_multi_var_declaration_three_variables(self):
        code = "x, y, z: float = 1.0, 2.0, 3.0\n"
        storage = compile_snippet(code)
        self.assertIn('x', storage.variables)
        self.assertIn('y', storage.variables)
        self.assertIn('z', storage.variables)
        self.assertEqual(storage.variables['x'].type, 'float')
        self.assertEqual(storage.variables['y'].type, 'float')
        self.assertEqual(storage.variables['z'].type, 'float')

    def test_multi_var_declaration_privacy(self):
        code = "private a, b: int = 1, 2\n"
        storage = compile_snippet(code)
        self.assertEqual(storage.variables['a'].privacy, 'private')
        self.assertEqual(storage.variables['b'].privacy, 'private')

    def test_multi_var_declaration_cardinality_mismatch_raises_error(self):
        code = "a, b: int = 10\n"
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_multi_var_declaration_type_mismatch_raises_error(self):
        code = "a, b: int = 10, 'incompatible'\n"
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_multi_var_declaration_collision_raises_error(self):
        code = "a, a: int = 1, 2\n"
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_multi_var_declaration_inside_function(self):
        code = (
            "int foo():\n"
            "    a, b: int = 1, 2\n"
            "    return a + b\n"
        )
        storage = compile_snippet(code)
        self.assertIn('foo', storage.functions)

    # =========================================================================
    # ASG-05: Punteros constantes (cptr) y punteros regulares (ptr)
    # =========================================================================
    def test_cptr_with_base_type(self):
        code = "cptr b: int = 20\n"
        storage = compile_snippet(code)
        self.assertIn('b', storage.variables)
        var_b = storage.variables['b']
        self.assertEqual(var_b.type, 'int')
        self.assertEqual(var_b.pointer_base_type, 'int')
        self.assertTrue(var_b.is_constant)
        self.assertTrue(var_b.is_cptr)
        self.assertFalse(var_b.is_ptr)
        self.assertTrue(var_b.is_pointer)

    def test_cptr_without_base_type(self):
        code = "cptr b = 20\n"
        storage = compile_snippet(code)
        self.assertIn('b', storage.variables)
        var_b = storage.variables['b']
        self.assertEqual(var_b.type, 'void')
        self.assertEqual(var_b.pointer_base_type, 'void')
        self.assertTrue(var_b.is_constant)
        self.assertTrue(var_b.is_cptr)
        self.assertFalse(var_b.is_ptr)
        self.assertTrue(var_b.is_pointer)

    def test_ptr_with_base_type(self):
        code = "ptr p: int = 0\n"
        storage = compile_snippet(code)
        self.assertIn('p', storage.variables)
        var_p = storage.variables['p']
        self.assertEqual(var_p.type, 'int')
        self.assertEqual(var_p.pointer_base_type, 'int')
        self.assertFalse(var_p.is_constant)
        self.assertTrue(var_p.is_ptr)
        self.assertFalse(var_p.is_cptr)
        self.assertTrue(var_p.is_pointer)

    def test_ptr_with_null(self):
        code = "ptr p = Null\n"
        storage = compile_snippet(code)
        self.assertIn('p', storage.variables)
        var_p = storage.variables['p']
        self.assertEqual(var_p.type, 'void')
        self.assertEqual(var_p.pointer_base_type, 'void')
        self.assertTrue(var_p.is_ptr)
        self.assertTrue(var_p.is_pointer)

    def test_ptr_generic_partial(self):
        code = "ptr p\n"
        storage = compile_snippet(code)
        self.assertIn('p', storage.variables)
        var_p = storage.variables['p']
        self.assertEqual(var_p.type, 'void')
        self.assertTrue(var_p.is_ptr)
        self.assertIsNone(var_p.value)

    def test_cptr_multi_declaration(self):
        code = "cptr x, y: int = 10, 20\n"
        storage = compile_snippet(code)
        self.assertIn('x', storage.variables)
        self.assertIn('y', storage.variables)
        self.assertEqual(storage.variables['x'].type, 'int')
        self.assertEqual(storage.variables['x'].pointer_base_type, 'int')
        self.assertTrue(storage.variables['x'].is_cptr)
        self.assertEqual(storage.variables['y'].type, 'int')
        self.assertEqual(storage.variables['y'].pointer_base_type, 'int')
        self.assertTrue(storage.variables['y'].is_cptr)

    def test_array_object_encapsulation(self):
        code = "numbers: array[int, 10]\n"
        storage = compile_snippet(code)
        self.assertIn('numbers', storage.variables)
        v = storage.variables['numbers']
        self.assertIsNotNone(v.array)
        self.assertEqual(v.array.element_type, 'int')
        self.assertEqual(v.array.size, 10)
        self.assertFalse(v.array.is_cptr)
        self.assertFalse(v.array.is_ptr)
        self.assertEqual(v.fixed_size, 10)


if __name__ == '__main__':
    unittest.main()


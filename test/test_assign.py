import unittest
from test.helpers import compile_snippet


class TestAssign(unittest.TestCase):
    def test_reassignment(self):
        code = (
            "a: int = 10\n"
            "a = 25\n"
        )
        storage = compile_snippet(code)
        self.assertIn('a', storage.variables)
        self.assertGreater(storage.variables['a'].uses, 0)

    def test_compound_assignment(self):
        code = (
            "a: int = 10\n"
            "a += 5\n"
        )
        storage = compile_snippet(code)
        self.assertIn('a', storage.variables)

    def test_undeclared_variable_assignment(self):
        code = "a = 10\n"
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_constant_reassignment(self):
        code = (
            "CONSTANTE: int = 10\n"
            "CONSTANTE = 20\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_assignment_type_mismatch(self):
        code = (
            "a: int = 10\n"
            "a = 'incompatible'\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    # =========================================================================
    # ASG-01: Validación de operadores compuestos
    # =========================================================================
    def test_compound_assignment_all_int_operators(self):
        code = (
            "a: int = 10\n"
            "a += 5\n"
            "a -= 2\n"
            "a *= 3\n"
            "a /= 2\n"
            "a %= 4\n"
            "a &= 7\n"
            "a |= 8\n"
            "a ^= 1\n"
            "a <<= 1\n"
            "a >>= 1\n"
        )
        storage = compile_snippet(code)
        self.assertIn('a', storage.variables)

    def test_compound_assignment_float_operators(self):
        code = (
            "f: float = 10.5\n"
            "f += 2.5\n"
            "f -= 1.0\n"
            "f *= 2.0\n"
            "f /= 2.0\n"
        )
        storage = compile_snippet(code)
        self.assertIn('f', storage.variables)

    def test_compound_assignment_string_concat(self):
        code = (
            "s: chain = \"hello\"\n"
            "s += \" world\"\n"
            "s += '!'\n"
        )
        storage = compile_snippet(code)
        self.assertIn('s', storage.variables)

    def test_compound_assignment_pointer_arithmetic(self):
        code = (
            "ptr p\n"
            "p += 4\n"
            "p -= 2\n"
        )
        storage = compile_snippet(code)
        self.assertIn('p', storage.variables)

    def test_compound_assignment_string_with_int_raises_type_error(self):
        code = (
            "s: chain = \"hello\"\n"
            "s += 5\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)


    def test_compound_assignment_bool_with_int_raises_type_error(self):
        code = (
            "b: bool = true\n"
            "b *= 2\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_compound_assignment_float_modulo_raises_type_error(self):
        code = (
            "f: float = 3.14\n"
            "f %= 2.0\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_compound_assignment_float_bitwise_raises_type_error(self):
        code = (
            "f: float = 3.14\n"
            "f &= 1\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_compound_assignment_struct_raises_type_error(self):
        code = (
            "struct Point:\n"
            "    x: int\n"
            "p: Point\n"
            "p += 1\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    # =========================================================================
    # ASG-02: Cadenas de miembros anidadas en clases / self / cls
    # =========================================================================
    def test_nested_member_chain_in_instance(self):
        code = (
            "struct Config:\n"
            "    timeout: int\n"
            "class App:\n"
            "    void __init__(c: Config):\n"
            "        self.cfg = c\n"
            "    void update_timeout():\n"
            "        self.cfg.timeout = 5000\n"
        )
        storage = compile_snippet(code)
        self.assertIn('App', storage.classes)

    def test_nested_member_chain_in_class_field(self):
        code = (
            "struct SubConfig:\n"
            "    val: int\n"
            "class MyClass:\n"
            "    sub: SubConfig\n"
            "MyClass.sub.val = 42\n"
        )
        storage = compile_snippet(code)
        self.assertIn('MyClass', storage.classes)

    def test_nested_member_chain_nonexistent_field_raises_attribute_error(self):
        code = (
            "struct Config:\n"
            "    timeout: int\n"
            "class App:\n"
            "    void __init__(c: Config):\n"
            "        self.cfg = c\n"
            "    void bad():\n"
            "        self.cfg.nonexistent = 10\n"
        )
        with self.assertRaises(AttributeError):
            compile_snippet(code)

    # =========================================================================
    # ASG-05: Puntero constante a datos mutables (cptr)
    # =========================================================================
    def test_cptr_declaration_and_properties(self):
        code = "cptr p\n"
        storage = compile_snippet(code)
        self.assertIn('p', storage.variables)
        var = storage.variables['p']
        self.assertEqual(var.type, 'void')
        self.assertTrue(var.is_cptr)
        self.assertTrue(var.is_constant)
        self.assertTrue(var.is_pointer)

    def test_cptr_reassignment_raises_error(self):
        code = (
            "cptr p\n"
            "ptr q\n"
            "p = q\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_cptr_compound_assignment_raises_error(self):
        code = (
            "cptr p\n"
            "p += 4\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_cptr_element_mutation_allowed(self):
        code = (
            "cptr p\n"
            "p[0] = 42\n"
        )
        storage = compile_snippet(code)
        self.assertIn('p', storage.variables)

    def test_backend_visit_assign_emission(self):
        from core.backend.ec.visitors.assign import visit_assign
        code = (
            "a: int = 10\n"
            "a = 25\n"
        )
        storage = compile_snippet(code)
        var_a = storage.variables['a']
        assign_node = [stmt for stmt in storage.statements if hasattr(stmt, 'target') or type(stmt).__name__ == 'Assign'][0]
        c_code = visit_assign(assign_node, storage=storage)
        self.assertEqual(c_code, f"{var_a.c_name} = 25;")

    def test_backend_visit_compound_assign_emission(self):
        from core.backend.ec.visitors.assign import visit_assign
        code = (
            "counter: int = 1\n"
            "counter += 5\n"
        )
        storage = compile_snippet(code)
        var_c = storage.variables['counter']
        assign_node = [stmt for stmt in storage.statements if type(stmt).__name__ == 'Assign'][0]
        c_code = visit_assign(assign_node, storage=storage)
        self.assertEqual(c_code, f"{var_c.c_name} += 5;")


if __name__ == '__main__':
    unittest.main()

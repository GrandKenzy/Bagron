import unittest
from test.helpers import compile_snippet
from core.backend.ec.visitors.function import visit_function
from core.backend.ec.visitors.variable import resolve_value


class TestIntrinsics(unittest.TestCase):
    def test_print_simple_string(self):
        code = (
            "void test():\n"
            "    print(\"Hola mundo\")\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['test']
        decl, _ = visit_function(func, storage=storage)
        self.assertIn('printf("%s\\n", "Hola mundo");', decl)

    def test_print_multiple_arguments_with_variables(self):
        code = (
            "void test():\n"
            "    x: int = 42\n"
            "    b: bool = true\n"
            "    print(\"Resultado:\", x, b)\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['test']
        decl, _ = visit_function(func, storage=storage)
        self.assertIn('printf("%s %d %s\\n", "Resultado:", x, (b ? "true" : "false"));', decl)

    def test_sizeof_primitive_and_struct(self):
        code = (
            "struct Point:\n"
            "    x: int\n"
            "    y: int\n"
            "\n"
            "void test():\n"
            "    s1: wsize = sizeof(int)\n"
            "    s2: wsize = sizeof(Point)\n"
        )
        storage = compile_snippet(code)
        pt_struct = storage.structs['Point']
        func = storage.functions['test']
        decl, _ = visit_function(func, storage=storage)
        self.assertIn("size_t s1 = sizeof(int);", decl)
        self.assertIn(f"size_t s2 = sizeof({pt_struct.c_name});", decl)

    def test_free_pointer(self):
        code = (
            "void test():\n"
            "    ptr buffer: int\n"
            "    free(buffer)\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['test']
        decl, _ = visit_function(func, storage=storage)
        self.assertIn("free(buffer);", decl)

    def test_input_with_and_without_prompt(self):
        code = (
            "void test():\n"
            "    nombre: chain = input(\"Ingrese su nombre: \")\n"
            "    linea: chain = input()\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['test']
        decl, _ = visit_function(func, storage=storage)
        self.assertIn('char* nombre = _ec_input("Ingrese su nombre: ");', decl)
        self.assertIn('char* linea = _ec_input("");', decl)

    def test_egl_version(self):
        code = (
            "void test():\n"
            "    v: chain = EGL_Version()\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['test']
        decl, _ = visit_function(func, storage=storage)
        self.assertIn('char* v = "1.0.0";', decl)


if __name__ == '__main__':
    unittest.main()

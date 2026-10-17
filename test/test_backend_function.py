import shutil
import tempfile
import unittest
from pathlib import Path

from test.helpers import compile_snippet
from core.backend.ec.visitors.function import visit_function
from core.compiler import compile as compile_project


class TestBackendFunction(unittest.TestCase):
    def test_basic_function_mangling_and_signature(self):
        code = (
            "int suma(a: int, b: int):\n"
            "    return a + b\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['suma']
        self.assertTrue(func.c_name.startswith('_ec_'))
        self.assertTrue(func.c_name.endswith('_suma'))

        decl, header = visit_function(func, storage=storage)
        self.assertIn(f"int {func.c_name}(int a, int b) {{", decl)
        self.assertIn("return (a + b);", decl)
        self.assertEqual(header, f"int {func.c_name}(int a, int b);")

    def test_main_function_preserves_name(self):
        code = (
            "int main():\n"
            "    return 0\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['main']
        self.assertEqual(func.c_name, 'main')

        decl, header = visit_function(func, storage=storage)
        self.assertIn("int main(void) {", decl)
        self.assertIn("return 0;", decl)
        self.assertNotIn("static", decl)
        self.assertIsNone(header)

    def test_private_and_inline_function(self):
        code = (
            "private __inline__ void internal_log(msg: chain):\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['internal_log']
        self.assertEqual(func.privacy, 'private')
        self.assertTrue(func.is_inline)

        decl, header = visit_function(func, storage=storage)
        self.assertTrue(decl.startswith(f"static inline void {func.c_name}(char* msg)"))
        self.assertIsNone(header)

    def test_function_with_struct_and_enum_types(self):
        code = (
            "enum Status:\n"
            "    OK = 0\n"
            "    ERROR = 1\n"
            "\n"
            "struct Point:\n"
            "    x: int\n"
            "    y: int\n"
            "\n"
            "Point create_point(status: Status, x: int, y: int):\n"
            "    p: Point\n"
            "    return p\n"
        )
        storage = compile_snippet(code)
        status_enum = storage.enums['Status']
        point_struct = storage.structs['Point']
        func = storage.functions['create_point']

        decl, header = visit_function(func, storage=storage)
        # El tipo de retorno debe usar point_struct.c_name
        self.assertIn(f"{point_struct.c_name} {func.c_name}({status_enum.c_name} status, int x, int y)", decl)
        self.assertIn(f"{point_struct.c_name} p;", decl)
        self.assertIn("return p;", decl)
        self.assertIn(f"{point_struct.c_name} {func.c_name}({status_enum.c_name} status, int x, int y);", header)

    def test_function_with_local_control_flow(self):
        code = (
            "int absolute(val: int):\n"
            "    if val < 0:\n"
            "        return -val\n"
            "    else:\n"
            "        return val\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['absolute']
        decl, _ = visit_function(func, storage=storage)
        self.assertIn("if ((val < 0)) {", decl)
        self.assertIn("return (-val);", decl)
        self.assertIn("} else {", decl)
        self.assertIn("return val;", decl)

    def test_cross_module_function_call(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="ec_test_func_mod_"))
        try:
            modules_dir = tmp_dir / "modules"
            modules_dir.mkdir(parents=True, exist_ok=True)

            math_code = (
                "int add(a: int, b: int):\n"
                "    return a + b\n"
            )
            (modules_dir / "math.egl").write_text(math_code, encoding="utf-8")

            main_code = (
                "import { add } from math\n"
                "int main():\n"
                "    res: int = add(10, 20)\n"
                "    return res\n"
            )
            (tmp_dir / "main.egl").write_text(main_code, encoding="utf-8")

            storage = compile_project(tmp_dir)
            math_mod = storage.modules["math"]
            add_func = math_mod.functions["add"]

            # Comprobar que add fue mangled
            self.assertTrue(add_func.c_name.startswith("_ec_"))
            self.assertTrue(add_func.c_name.endswith("_add"))

            # Comprobar emisión de main en C
            main_func = storage.functions["main"]
            decl, _ = visit_function(main_func, storage=storage)
            self.assertIn(f"int res = {add_func.c_name}(10, 20);", decl)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()

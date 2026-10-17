import unittest
from test.helpers import compile_snippet
from core.backend.ec.visitors.variable import convert_type, resolve_value, visit_var
from core.processor.objects.variable import Variable


class TestBackendVariable(unittest.TestCase):
    def test_convert_type_primitives(self):
        self.assertEqual(convert_type('int'), 'int')
        self.assertEqual(convert_type('int8'), 'int8_t')
        self.assertEqual(convert_type('int16'), 'int16_t')
        self.assertEqual(convert_type('int32'), 'int32_t')
        self.assertEqual(convert_type('int64'), 'int64_t')
        self.assertEqual(convert_type('uint'), 'uint32_t')
        self.assertEqual(convert_type('uint8'), 'uint8_t')
        self.assertEqual(convert_type('byte'), 'uint8_t')
        self.assertEqual(convert_type('uint16'), 'uint16_t')
        self.assertEqual(convert_type('uint32'), 'uint32_t')
        self.assertEqual(convert_type('uint64'), 'uint64_t')
        self.assertEqual(convert_type('middle'), '_Float16')
        self.assertEqual(convert_type('float'), 'float')
        self.assertEqual(convert_type('double'), 'double')
        self.assertEqual(convert_type('bool'), 'bool')
        self.assertEqual(convert_type('char'), 'char')
        self.assertEqual(convert_type('chain'), 'char*')
        self.assertEqual(convert_type('ptr'), 'void*')
        self.assertEqual(convert_type('cptr'), 'void* const')
        self.assertEqual(convert_type('wsize'), 'size_t')

    def test_convert_type_pointers_and_arrays(self):
        self.assertEqual(convert_type('int*'), 'int*')
        self.assertEqual(convert_type('Point*'), 'Point*')
        self.assertEqual(convert_type('array[int, 10]'), 'int')
        self.assertEqual(convert_type('array[float]'), 'float')
        self.assertEqual(convert_type('CustomType'), 'CustomType')

    def test_visit_var_primitive_scalars(self):
        code = (
            "a: int = 10\n"
            "f: float = 3.14\n"
            "ok: bool = true\n"
            "c: char = 'x'\n"
            "s: chain = 'hola'\n"
            "b: byte = 255\n"
        )
        storage = compile_snippet(code)
        
        # a: int = 10
        var_a = storage.variables['a']
        decl_a, hdr_a = visit_var(var_a)
        self.assertEqual(decl_a, f"int {var_a.c_name} = 10;")
        self.assertEqual(hdr_a, f"extern int {var_a.c_name};")
        self.assertTrue(var_a.c_name.startswith("_ec_main_"))
        self.assertTrue(var_a.c_name.endswith("_a"))

        # f: float = 3.14
        var_f = storage.variables['f']
        decl_f, hdr_f = visit_var(var_f)
        self.assertEqual(decl_f, f"float {var_f.c_name} = 3.14;")
        self.assertEqual(hdr_f, f"extern float {var_f.c_name};")

        # ok: bool = true
        var_ok = storage.variables['ok']
        decl_ok, hdr_ok = visit_var(var_ok)
        self.assertEqual(decl_ok, f"bool {var_ok.c_name} = true;")
        self.assertEqual(hdr_ok, f"extern bool {var_ok.c_name};")

        # c: char = 'x'
        var_c = storage.variables['c']
        decl_c, hdr_c = visit_var(var_c)
        self.assertEqual(decl_c, f"char {var_c.c_name} = 'x';")
        self.assertEqual(hdr_c, f"extern char {var_c.c_name};")

        # s: chain = 'hola'
        var_s = storage.variables['s']
        decl_s, hdr_s = visit_var(var_s)
        self.assertEqual(decl_s, f'char* {var_s.c_name} = "hola";')
        self.assertEqual(hdr_s, f"extern char* {var_s.c_name};")

        # b: byte = 255
        var_b = storage.variables['b']
        decl_b, hdr_b = visit_var(var_b)
        self.assertEqual(decl_b, f"uint8_t {var_b.c_name} = 255;")
        self.assertEqual(hdr_b, f"extern uint8_t {var_b.c_name};")


    def test_visit_var_constant(self):
        code = "MAX_SIZE: int = 100\n"
        storage = compile_snippet(code)
        var_max = storage.variables['MAX_SIZE']
        decl, hdr = visit_var(var_max)
        self.assertEqual(decl, f"const int {var_max.c_name} = 100;")
        self.assertEqual(hdr, f"extern const int {var_max.c_name};")

    def test_visit_var_uninitialized(self):
        code = "count: int\n"
        storage = compile_snippet(code)
        var_count = storage.variables['count']
        decl, hdr = visit_var(var_count)
        self.assertEqual(decl, f"int {var_count.c_name};")
        self.assertEqual(hdr, f"extern int {var_count.c_name};")

    def test_visit_var_private_visibility(self):
        v = Variable(name='secret', value=42, type='int', privacy='private', is_constant=False)
        decl, hdr = visit_var(v)
        self.assertEqual(decl, "static int secret = 42;")
        self.assertIsNone(hdr)

    def test_visit_var_cptr(self):
        v = Variable(name='buf_ptr', value='raw_buffer', type='cptr', privacy='public', is_constant=True)
        decl, hdr = visit_var(v)
        self.assertEqual(decl, "void* const buf_ptr = raw_buffer;")
        self.assertEqual(hdr, "extern void* const buf_ptr;")

    def test_visit_var_cptr_with_base_type(self):
        code = "cptr b: int = 20\n"
        storage = compile_snippet(code)
        var_b = storage.variables['b']
        decl, hdr = visit_var(var_b)
        self.assertEqual(decl, f"int* const {var_b.c_name} = 20;")
        self.assertEqual(hdr, f"extern int* const {var_b.c_name};")

    def test_visit_var_ptr_with_base_type(self):
        code = "ptr p: int = 0\n"
        storage = compile_snippet(code)
        var_p = storage.variables['p']
        decl, hdr = visit_var(var_p)
        self.assertEqual(decl, f"int* {var_p.c_name} = 0;")
        self.assertEqual(hdr, f"extern int* {var_p.c_name};")


    def test_visit_var_fixed_size_array(self):
        code = "numbers: array[int, 10]\n"
        storage = compile_snippet(code)
        var_arr = storage.variables['numbers']
        decl, hdr = visit_var(var_arr)
        self.assertEqual(decl, f"int {var_arr.c_name}[10];")
        self.assertEqual(hdr, f"extern int {var_arr.c_name}[10];")

    def test_visit_var_binary_expression(self):
        code = "result: int = 10 + 25\n"
        storage = compile_snippet(code)
        var_res = storage.variables['result']
        decl, hdr = visit_var(var_res)
        self.assertEqual(decl, f"int {var_res.c_name} = (10 + 25);")
        self.assertEqual(hdr, f"extern int {var_res.c_name};")

    def test_visit_var_null_value(self):
        code = "ptr p = Null\n"
        storage = compile_snippet(code)
        var_p = storage.variables['p']
        decl, hdr = visit_var(var_p)
        self.assertEqual(decl, f"void* {var_p.c_name} = NULL;")
        self.assertEqual(hdr, f"extern void* {var_p.c_name};")

    def test_generated_c_compiles_and_runs_with_gcc(self):
        import os
        import shutil
        import subprocess
        import tempfile

        gcc_path = shutil.which('gcc')
        if not gcc_path:
            self.skipTest("GCC no disponible en el sistema")

        code = (
            "a: int = 42\n"
            "f: float = 3.5\n"
            "ok: bool = true\n"
            "c: char = 'Z'\n"
            "msg: chain = 'Hola Easy-C'\n"
            "bt: byte = 200\n"
            "nums: array[int, 3]\n"
        )
        storage = compile_snippet(code)
        c_lines = [visit_var(v)[0] for v in storage.bpoint]
        v_a = storage.variables['a'].c_name
        v_nums = storage.variables['nums'].c_name
        v_msg = storage.variables['msg'].c_name
        v_f = storage.variables['f'].c_name
        v_c = storage.variables['c'].c_name
        v_ok = storage.variables['ok'].c_name
        v_bt = storage.variables['bt'].c_name

        c_source = (
            "#include <stdio.h>\n"
            "#include <stdbool.h>\n"
            "#include <stdint.h>\n"
            + "\n".join(c_lines) + "\n"
            + "int main() {\n"
            + f"    {v_nums}[0] = {v_a};\n"
            + f'    printf("%s: %d, %.1f, %c, %d, %u\\n", {v_msg}, {v_nums}[0], {v_f}, {v_c}, {v_ok} ? 1 : 0, {v_bt});\n'
            + "    return 0;\n"
            + "}\n"
        )
        with tempfile.NamedTemporaryFile(suffix='.c', delete=False, mode='w', encoding='utf-8') as f:
            f.write(c_source)
            c_file = f.name

        exe_file = c_file.replace('.c', '.exe')
        try:
            compile_res = subprocess.run([gcc_path, '-Wall', '-Wextra', c_file, '-o', exe_file], capture_output=True, text=True)
            self.assertEqual(compile_res.returncode, 0, f"Error compilando con GCC:\n{compile_res.stderr}")
            run_res = subprocess.run([exe_file], capture_output=True, text=True)
            self.assertEqual(run_res.returncode, 0)
            self.assertEqual(run_res.stdout.strip(), "Hola Easy-C: 42, 3.5, Z, 1, 200")

        finally:
            if os.path.exists(c_file):
                os.remove(c_file)
            if os.path.exists(exe_file):
                os.remove(exe_file)


    def test_bpoint_order_and_backend_compile(self):
        code = (
            "x: int = 10\n"
            "int add(a: int, b: int):\n"
            "    return a + b\n"
            "struct Point:\n"
            "    x: int\n"
            "    y: int\n"
            "enum Color:\n"
            "    RED\n"
            "TypeAlias int MiInt\n"
            "y: int = 20\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.bpoint), 6)
        from core.processor.objects.function import Function
        from core.processor.objects.struct_decl import StructDecl
        from core.processor.objects.enum_decl import EnumDecl
        from core.processor.objects.type_decl import TypeAlias

        self.assertIsInstance(storage.bpoint[0], Variable)
        self.assertEqual(storage.bpoint[0].name, 'x')
        self.assertIsInstance(storage.bpoint[1], Function)
        self.assertEqual(storage.bpoint[1].name, 'add')
        self.assertIsInstance(storage.bpoint[2], StructDecl)
        self.assertEqual(storage.bpoint[2].name, 'Point')
        self.assertIsInstance(storage.bpoint[3], EnumDecl)
        self.assertEqual(storage.bpoint[3].name, 'Color')
        self.assertIsInstance(storage.bpoint[4], TypeAlias)
        self.assertEqual(storage.bpoint[4].name, 'MiInt')
        self.assertIsInstance(storage.bpoint[5], Variable)
        self.assertEqual(storage.bpoint[5].name, 'y')

        # Compilar en el backend EC sin errores
        from core.backend import ec
        ec.compile(storage)


if __name__ == '__main__':
    unittest.main()


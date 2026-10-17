import unittest
from test.helpers import compile_snippet
from core.processor.objects.call import Call
from core.processor.objects.function import Function
from core.processor.objects.if_statement import IfStatement
from core.processor.objects.member_access import MemberAccess
from core.processor.objects.method_call import MethodCall
from core.processor.objects.while_statement import WhileStatement
from core.processor.objects.for_statement import ForStatement


class TestCall(unittest.TestCase):
    def test_basic_top_level_print_call(self):
        code = 'print("hola mundo")\n'
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        call_obj = storage.statements[0]
        self.assertIsInstance(call_obj, Call)
        self.assertEqual(call_obj.name, 'print')
        self.assertEqual(call_obj.returntype, 'void')
        self.assertIsNone(call_obj.scoped)

    def test_user_defined_function_call(self):
        code = (
            "int add(a: int, b: int):\n"
            "    return a + b\n"
            "add(10, 20)\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        call_obj = storage.statements[0]
        self.assertIsInstance(call_obj, Call)
        self.assertEqual(call_obj.name, 'add')
        self.assertEqual(call_obj.returntype, 'int')
        func = storage.functions['add']
        self.assertEqual(func.uses, 1)

    def test_function_call_inside_function(self):
        code = (
            "void log_msg(msg: chain):\n"
            "    print(msg)\n"
        )

        storage = compile_snippet(code)
        func = storage.functions['log_msg']
        self.assertEqual(len(func.body), 1)
        call_obj = func.body[0]
        self.assertIsInstance(call_obj, Call)
        self.assertEqual(call_obj.name, 'print')
        self.assertEqual(call_obj.scoped, func)

    def test_function_call_inside_if(self):
        code = (
            "if true:\n"
            "    print(\"dentro de if\")\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        if_stmt = storage.statements[0]
        self.assertIsInstance(if_stmt, IfStatement)
        self.assertEqual(len(if_stmt.body), 1)
        call_obj = if_stmt.body[0]
        self.assertIsInstance(call_obj, Call)
        self.assertEqual(call_obj.name, 'print')
        self.assertIsNone(call_obj.scoped)

    def test_function_call_inside_if_inside_function(self):
        code = (
            "void check(cond: bool):\n"
            "    if cond:\n"
            "        print(\"yes\")\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['check']
        if_stmt = func.body[0]
        self.assertIsInstance(if_stmt, IfStatement)
        call_obj = if_stmt.body[0]
        self.assertIsInstance(call_obj, Call)
        self.assertEqual(call_obj.scoped, func)

    def test_function_call_inside_while(self):
        code = (
            "i: int = 0\n"
            "while i < 3:\n"
            "    print(\"loop\")\n"
            "    i += 1\n"
        )
        storage = compile_snippet(code)
        while_stmt = storage.statements[0]
        self.assertIsInstance(while_stmt, WhileStatement)
        call_obj = while_stmt.body[0]
        self.assertIsInstance(call_obj, Call)
        self.assertEqual(call_obj.name, 'print')
        self.assertIsNone(call_obj.scoped)

    def test_function_call_inside_for(self):
        code = (
            "for i ran 5:\n"
            "    print(i)\n"
        )
        storage = compile_snippet(code)
        for_stmt = storage.statements[0]
        self.assertIsInstance(for_stmt, ForStatement)
        call_obj = for_stmt.body[0]
        self.assertIsInstance(call_obj, Call)
        self.assertEqual(call_obj.name, 'print')

    def test_call_with_variable_assignment(self):
        code = (
            "int get_val():\n"
            "    return 42\n"
            "x: int = get_val()\n"
        )
        storage = compile_snippet(code)
        self.assertIn('x', storage.variables)
        self.assertEqual(storage.variables['x'].type, 'int')

    def test_call_type_mismatch_in_assignment_raises_error(self):
        code = (
            "chain get_text():\n"
            "    return \"hola\"\n"
            "x: int = get_text()\n"
        )

        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_call_arg_count_mismatch_raises_error(self):
        code_too_few = (
            "int add(a: int, b: int):\n"
            "    return a + b\n"
            "add(1)\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code_too_few)

        code_too_many = (
            "int add(a: int, b: int):\n"
            "    return a + b\n"
            "add(1, 2, 3)\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code_too_many)

    def test_call_arg_type_mismatch_raises_error(self):
        code = (
            "int double_it(n: int):\n"
            "    return n * 2\n"
            "double_it(\"no es int\")\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_call_variable_as_function_raises_error(self):
        code = (
            "count: int = 10\n"
            "count()\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_call_undeclared_function_raises_error(self):
        code = 'funcion_inexistente()\n'
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_user_defined_function_cannot_override_reserved(self):
        code = (
            "int print(val: int):\n"
            "    return val * 10\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("No se puede reemplazar la función intrínseca reservada 'print'", str(ctx.exception))

    def test_fallback_to_reserve_funnames_when_not_in_user_scope(self):
        code = (
            "void test_reserve():\n"
            "    print(\"mensaje\")\n"
        )
        storage = compile_snippet(code)
        self.assertNotIn('print', storage.functions)
        call_obj = storage.functions['test_reserve'].body[0]
        self.assertIsInstance(call_obj, Call)
        self.assertEqual(call_obj.name, 'print')
        self.assertEqual(call_obj.returntype, 'void')

    def test_member_chain_method_call(self):
        code = 'std.io.println("test")\n'
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        mc = storage.statements[0]
        self.assertIsInstance(mc, MethodCall)
        self.assertEqual(mc.target, 'std.io')
        self.assertEqual(mc.method, 'println')
        self.assertIsNone(mc.scoped)

    def test_member_chain_property_access(self):
        code = 'std.math.PI\n'
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        ma = storage.statements[0]
        self.assertIsInstance(ma, MemberAccess)
        self.assertEqual(ma.target, 'std.math')
        self.assertEqual(ma.member, 'PI')

    def test_struct_constructor_called_inside_function(self):
        code = (
            "struct Point:\n"
            "    x: int\n"
            "    y: int\n"
            "void make_point():\n"
            "    Point(10, 20)\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['make_point']
        self.assertEqual(len(func.body), 1)
        call_obj = func.body[0]
        self.assertIsInstance(call_obj, Call)
        self.assertEqual(call_obj.name, 'Point')
        self.assertEqual(call_obj.returntype, 'Point')

    def test_struct_constructor_with_variable_declaration_inside_function(self):
        code = (
            "struct Point:\n"
            "    x: int\n"
            "    y: int\n"
            "void make_point():\n"
            "    p: Point = Point(10, 20)\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['make_point']
        self.assertEqual(len(func.body), 1)
        self.assertIn('p', func.scope.variables)
        self.assertEqual(func.scope.variables['p'].type, 'Point')

    def test_call_function_parameter_as_function_raises_error(self):
        code = (
            "void run(x: int):\n"
            "    x()\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_call_enum_as_function_raises_error(self):
        code = (
            "enum Color:\n"
            "    RED\n"
            "    GREEN\n"
            "Color()\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_reassign_variable_with_typealias(self):
        code = (
            "TypeAlias int MiTipo\n"
            "a: MiTipo = 10\n"
            "a = 20\n"
        )
        storage = compile_snippet(code)
        self.assertIn('a', storage.variables)
        self.assertEqual(storage.variables['a'].type, 'MiTipo')

    # ========================================================
    # CAL-02: Llamadas encadenadas fluidas ("Fluent Interface")
    # ========================================================
    def test_fluent_chained_method_calls_order(self):
        code = 'builder.step1().step2()\n'
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        step2 = storage.statements[0]
        self.assertIsInstance(step2, MethodCall)
        self.assertEqual(step2.method, 'step2')
        step1 = step2.target
        self.assertIsInstance(step1, MethodCall)
        self.assertEqual(step1.method, 'step1')
        self.assertEqual(step1.target, 'builder')

    def test_chained_call_then_property_access(self):
        code = 'get_player().get_pos().x\n'
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        x_access = storage.statements[0]
        self.assertIsInstance(x_access, MemberAccess)
        self.assertEqual(x_access.member, 'x')
        get_pos = x_access.target
        self.assertIsInstance(get_pos, MethodCall)
        self.assertEqual(get_pos.method, 'get_pos')
        get_player = get_pos.target
        self.assertIsInstance(get_player, Call)
        self.assertEqual(get_player.name, 'get_player')

    # ========================================================
    # CAL-04: Argumentos variádicos (*args: tipo)
    # ========================================================
    def test_variadic_args_call_with_matching_types(self):
        code = (
            "void log_all(prefix: chain, *msgs: chain):\n"
            "    pass\n"
            "log_all(\"INFO\")\n"
            "log_all(\"INFO\", \"m1\")\n"
            "log_all(\"INFO\", \"m1\", \"m2\", \"m3\")\n"
        )
        storage = compile_snippet(code)
        self.assertIn('log_all', storage.functions)
        self.assertEqual(len(storage.statements), 3)

    def test_variadic_args_call_with_mismatched_type_raises_error(self):
        code = (
            "void log_all(prefix: chain, *msgs: chain):\n"
            "    pass\n"
            "log_all(\"INFO\", \"ok\", 123)\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_variadic_args_call_missing_required_raises_error(self):
        code = (
            "void log_all(prefix: chain, *msgs: chain):\n"
            "    pass\n"
            "log_all()\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    # ========================================================
    # CAL-06: Validación estática de límites de índices
    # ========================================================
    def test_array_index_in_bounds(self):
        code = (
            "arr: array[int, 5]\n"
            "x: int = arr[0]\n"
            "y: int = arr[4]\n"
        )
        storage = compile_snippet(code)
        self.assertIn('arr', storage.variables)
        self.assertIn('x', storage.variables)
        self.assertIn('y', storage.variables)

    def test_array_index_negative_raises_error(self):
        code = (
            "arr: array[int, 5]\n"
            "x: int = arr[-1]\n"
        )
        with self.assertRaises(IndexError):
            compile_snippet(code)

    def test_array_index_out_of_bounds_raises_error(self):
        code = (
            "arr: array[int, 5]\n"
            "x: int = arr[5]\n"
        )
        with self.assertRaises(IndexError):
            compile_snippet(code)

    def test_array_index_assignment_out_of_bounds_raises_error(self):
        code = (
            "arr: array[int, 5]\n"
            "arr[10] = 42\n"
        )
        with self.assertRaises(IndexError):
            compile_snippet(code)

    def test_array_index_non_integer_raises_type_error(self):
        code = (
            "arr: array[int, 5]\n"
            "x: int = arr[\"hola\"]\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)


if __name__ == '__main__':
    unittest.main()

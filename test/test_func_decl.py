import unittest
from test.helpers import compile_snippet


class TestFuncDecl(unittest.TestCase):
    def test_basic_function(self):
        code = (
            "int suma(a: int, b: int):\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        self.assertIn('suma', storage.functions)
        func = storage.functions['suma']
        self.assertEqual(func.name, 'suma')
        self.assertEqual(func.return_type, 'int')
        self.assertEqual(func.privacy, 'public')
        self.assertFalse(func.is_inline)

    def test_function_privacy_and_inline(self):
        code = (
            "private __inline__ void logger(msg: chain):\n"
            "    pass\n"
        )

        storage = compile_snippet(code)
        self.assertIn('logger', storage.functions)
        func = storage.functions['logger']
        self.assertEqual(func.name, 'logger')
        self.assertEqual(func.return_type, 'void')
        self.assertEqual(func.privacy, 'private')
        self.assertTrue(func.is_inline)

    def test_function_inherited_privacy(self):
        code = (
            "clause Visibility 'private'\n"
            "int calculate():\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['calculate']
        self.assertEqual(func.privacy, 'private')

    def test_function_collision_with_variable(self):
        code = (
            "total: int = 100\n"
            "int total():\n"
            "    pass\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("Colisión", str(ctx.exception))

    def test_function_duplicate_name_collision(self):
        code = (
            "int compute():\n"
            "    pass\n"
            "int compute():\n"
            "    pass\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("Colisión", str(ctx.exception))

    def test_decorated_function(self):
        code = (
            "@async\n"
            "@test\n"
            "int compute():\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        self.assertIn('compute', storage.functions)
        func = storage.functions['compute']
        self.assertEqual(func.name, 'compute')
        self.assertEqual(func.decorators, ['async', 'test'])

    def test_parameters_extracted(self):
        code = (
            "int add(x: int, y: int = 5):\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['add']
        self.assertEqual(len(func.parameters), 2)
        p1 = func.parameters[0]
        self.assertEqual(p1.name, 'x')
        self.assertEqual(p1.type, 'int')
        self.assertFalse(p1.has_default)

        p2 = func.parameters[1]
        self.assertEqual(p2.name, 'y')
        self.assertEqual(p2.type, 'int')
        self.assertTrue(p2.has_default)

        # Verificar presencia en scope local
        self.assertIn('x', func.scope.parameters)
        self.assertIn('y', func.scope.parameters)

    def test_local_variables_isolation(self):
        code = (
            "void execute():\n"
            "    local_num: int = 42\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['execute']
        self.assertIn('local_num', func.scope.variables)
        self.assertEqual(func.scope.variables['local_num'].type, 'int')
        # No debe existir en el storage global
        self.assertNotIn('local_num', storage.variables)

    def test_void_function_cannot_return_value(self):
        code = (
            "void do_something():\n"
            "    return 10\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("no puede retornar un valor", str(ctx.exception))

    def test_non_void_function_must_return_value(self):
        code = (
            "int get_number():\n"
            "    return\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("debe retornar un valor", str(ctx.exception))

    def test_duplicate_parameter_collision(self):
        code = (
            "void proc(a: int, a: float):\n"
            "    pass\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("ya existe", str(ctx.exception))

    def test_local_variable_collides_with_parameter(self):
        code = (
            "void handler(data: int):\n"
            "    data: int = 100\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("ya existe", str(ctx.exception))

    def test_parameter_order_positional_then_variadic_then_default(self):
        code = (
            "void my_func(a: int, *args: int, c: int = 10):\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['my_func']
        self.assertEqual(len(func.parameters), 3)
        self.assertEqual(func.parameters[0].name, 'a')
        self.assertFalse(func.parameters[0].is_variadic)
        self.assertEqual(func.parameters[1].name, 'args')
        self.assertTrue(func.parameters[1].is_variadic)
        self.assertEqual(func.parameters[2].name, 'c')
        self.assertTrue(func.parameters[2].has_default)

    def test_positional_param_after_variadic_raises_syntax_error(self):
        code = (
            "void my_func(*args: int, a: int):\n"
            "    pass\n"
        )
        with self.assertRaises(SyntaxError):
            compile_snippet(code)

    def test_positional_param_after_default_raises_syntax_error(self):
        code = (
            "void my_func(a: int = 1, b: int):\n"
            "    pass\n"
        )
        with self.assertRaises(SyntaxError):
            compile_snippet(code)

    def test_variadic_param_after_default_raises_syntax_error(self):
        code = (
            "void my_func(a: int = 1, *args: int):\n"
            "    pass\n"
        )
        with self.assertRaises(SyntaxError):
            compile_snippet(code)

    def test_multiple_variadic_params_raises_syntax_error(self):
        code = (
            "void my_func(*args1: int, *args2: int):\n"
            "    pass\n"
        )
        with self.assertRaises(SyntaxError):
            compile_snippet(code)

    def test_default_param_type_mismatch_raises_type_error(self):
        code = (
            "void my_func(a: int = \"invalido\"):\n"
            "    pass\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_cannot_replace_reserved_funname_with_function(self):
        code = (
            "void print(msg: chain):\n"
            "    pass\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("No se puede reemplazar la función intrínseca reservada 'print'", str(ctx.exception))

    def test_cannot_replace_reserved_funname_with_variable(self):
        code = (
            "free: int = 42\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("es una función intrínseca reservada y no puede ser reemplazada", str(ctx.exception))

    def test_cannot_use_reserved_funname_as_parameter(self):
        code = (
            "void calculate(free: int):\n"
            "    pass\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("es una función intrínseca reservada y no puede ser reemplazado", str(ctx.exception))

    def test_cannot_overwrite_reserved_func_in_manager(self):
        from core.initiator.reserve_funnames import MagicFuncsManager, ReservedFunc
        with self.assertRaises(RuntimeError) as ctx:
            _ = ReservedFunc('print', None, returned='void')
        self.assertIn("No se puede reemplazar la función intrínseca reservada 'print'", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()


import unittest
from test.helpers import compile_snippet
from core.processor.objects.while_statement import WhileStatement


class TestWhileStatement(unittest.TestCase):
    def test_basic_while_with_pass(self):
        code = (
            "while true:\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        while_stmt = storage.statements[0]
        self.assertIsInstance(while_stmt, WhileStatement)
        self.assertEqual(len(while_stmt.body), 1)

    def test_while_with_var_and_assignation(self):
        code = (
            "count: int = 0\n"
            "while count < 10:\n"
            "    count += 1\n"
        )
        storage = compile_snippet(code)
        self.assertIn('count', storage.variables)
        self.assertEqual(len(storage.statements), 1)
        while_stmt = storage.statements[0]
        self.assertIsInstance(while_stmt, WhileStatement)
        self.assertEqual(len(while_stmt.body), 1)

    def test_while_with_break_and_continue(self):
        code = (
            "while true:\n"
            "    break\n"
            "while true:\n"
            "    continue\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 2)
        w1 = storage.statements[0]
        w2 = storage.statements[1]
        self.assertIsInstance(w1, WhileStatement)
        self.assertIsInstance(w2, WhileStatement)

    def test_nested_while_loops(self):
        code = (
            "i: int = 0\n"
            "while i < 5:\n"
            "    j: int = 0\n"
            "    while j < 5:\n"
            "        j += 1\n"
            "    i += 1\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        outer_while = storage.statements[0]
        self.assertIsInstance(outer_while, WhileStatement)

        # Buscar el while anidado dentro del cuerpo
        nested_whiles = [stmt for stmt in outer_while.body if isinstance(stmt, WhileStatement)]
        self.assertEqual(len(nested_whiles), 1)
        inner_while = nested_whiles[0]
        self.assertIsInstance(inner_while, WhileStatement)

    def test_while_inside_function(self):
        code = (
            "int countdown(n: int):\n"
            "    while n > 0:\n"
            "        n -= 1\n"
            "    return n\n"
        )
        storage = compile_snippet(code)
        self.assertIn('countdown', storage.functions)
        func = storage.functions['countdown']

        # Encontrar WhileStatement en func.body
        while_stmts = [stmt for stmt in func.body if isinstance(stmt, WhileStatement)]
        self.assertEqual(len(while_stmts), 1)
        while_stmt = while_stmts[0]
        self.assertIsInstance(while_stmt, WhileStatement)
        self.assertEqual(len(while_stmt.body), 1)

    def test_while_with_local_vars_in_function(self):
        code = (
            "void run_loop():\n"
            "    x: int = 0\n"
            "    while x < 3:\n"
            "        step: int = 1\n"
            "        x += step\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['run_loop']
        self.assertIn('x', func.scope.variables)
        self.assertIn('step', func.scope.variables)
        self.assertNotIn('step', storage.variables)


if __name__ == '__main__':
    unittest.main()

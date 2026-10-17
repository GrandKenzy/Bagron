import unittest
from test.helpers import compile_snippet
from core.processor.objects.if_statement import ElifClause, IfStatement


class TestIfStatement(unittest.TestCase):
    def test_basic_if_with_pass(self):
        code = (
            "if true:\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        if_stmt = storage.statements[0]
        self.assertIsInstance(if_stmt, IfStatement)
        self.assertEqual(len(if_stmt.body), 1)
        self.assertEqual(len(if_stmt.elifs), 0)
        self.assertEqual(len(if_stmt.else_body), 0)

    def test_if_else(self):
        code = (
            "x: int = 10\n"
            "if x > 0:\n"
            "    x = 1\n"
            "else:\n"
            "    x = 0\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        if_stmt = storage.statements[0]
        self.assertIsInstance(if_stmt, IfStatement)
        self.assertEqual(len(if_stmt.body), 1)
        self.assertEqual(len(if_stmt.elifs), 0)
        self.assertEqual(len(if_stmt.else_body), 1)

    def test_if_elif_else(self):
        code = (
            "score: int = 85\n"
            "grade: int = 0\n"
            "if score >= 90:\n"
            "    grade = 1\n"
            "elif score >= 80:\n"
            "    grade = 2\n"
            "else:\n"
            "    grade = 3\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        if_stmt = storage.statements[0]
        self.assertIsInstance(if_stmt, IfStatement)
        self.assertEqual(len(if_stmt.body), 1)
        self.assertEqual(len(if_stmt.elifs), 1)
        self.assertIsInstance(if_stmt.elifs[0], ElifClause)
        self.assertEqual(len(if_stmt.elifs[0].body), 1)
        self.assertEqual(len(if_stmt.else_body), 1)

    def test_multiple_elifs(self):
        code = (
            "x: int = 2\n"
            "if x == 1:\n"
            "    pass\n"
            "elif x == 2:\n"
            "    pass\n"
            "elif x == 3:\n"
            "    pass\n"
            "else:\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        if_stmt = storage.statements[0]
        self.assertIsInstance(if_stmt, IfStatement)
        self.assertEqual(len(if_stmt.elifs), 2)
        self.assertEqual(len(if_stmt.else_body), 1)

    def test_nested_if(self):
        code = (
            "a: int = 1\n"
            "b: int = 2\n"
            "c: int = 0\n"
            "if a > 0:\n"
            "    if b > 0:\n"
            "        c = 3\n"
            "    else:\n"
            "        c = 4\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        outer_if = storage.statements[0]
        self.assertIsInstance(outer_if, IfStatement)
        nested_ifs = [stmt for stmt in outer_if.body if isinstance(stmt, IfStatement)]
        self.assertEqual(len(nested_ifs), 1)
        inner_if = nested_ifs[0]
        self.assertIsInstance(inner_if, IfStatement)
        self.assertEqual(len(inner_if.body), 1)
        self.assertEqual(len(inner_if.else_body), 1)

    def test_if_inside_while_with_break_continue(self):
        code = (
            "i: int = 0\n"
            "while i < 10:\n"
            "    if i == 5:\n"
            "        break\n"
            "    elif i == 2:\n"
            "        continue\n"
            "    i += 1\n"
        )
        storage = compile_snippet(code)
        while_stmt = storage.statements[0]
        if_stmts = [stmt for stmt in while_stmt.body if isinstance(stmt, IfStatement)]
        self.assertEqual(len(if_stmts), 1)
        if_stmt = if_stmts[0]
        self.assertEqual(len(if_stmt.body), 1)
        self.assertEqual(len(if_stmt.elifs), 1)
        self.assertEqual(len(if_stmt.elifs[0].body), 1)

    def test_if_inside_for_with_continue(self):
        code = (
            "for i ran (0, 10):\n"
            "    if i == 0:\n"
            "        continue\n"
        )
        storage = compile_snippet(code)
        for_stmt = storage.statements[0]
        if_stmts = [stmt for stmt in for_stmt.body if isinstance(stmt, IfStatement)]
        self.assertEqual(len(if_stmts), 1)

    def test_break_outside_loop_raises_error(self):
        code = (
            "if true:\n"
            "    break\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("no se puede utilizar fuera de un bucle", str(ctx.exception))

    def test_if_inside_function_with_return(self):
        code = (
            "int sign(x: int):\n"
            "    if x > 0:\n"
            "        return 1\n"
            "    elif x < 0:\n"
            "        return -1\n"
            "    else:\n"
            "        return 0\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['sign']
        self.assertEqual(len(func.body), 1)
        if_stmt = func.body[0]
        self.assertIsInstance(if_stmt, IfStatement)
        self.assertEqual(len(if_stmt.body), 1)
        self.assertEqual(len(if_stmt.elifs), 1)
        self.assertEqual(len(if_stmt.else_body), 1)

    def test_undefined_variable_in_condition_raises_error(self):
        code = (
            "if undefined_var > 0:\n"
            "    pass\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("Variable 'undefined_var' no está definida", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()

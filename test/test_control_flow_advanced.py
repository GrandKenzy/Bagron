import unittest
from test.helpers import compile_snippet
from core.processor.objects.function import Function
from core.processor.objects.if_statement import IfStatement, ElifClause
from core.processor.objects.while_statement import WhileStatement
from core.processor.objects.for_statement import ForStatement


class TestControlFlowAdvanced(unittest.TestCase):
    def test_deeply_nested_control_flow(self):
        code = (
            "int complex_algo(limit: int, threshold: int):\n"
            "    total: int = 0\n"
            "    while limit > 0:\n"
            "        if limit == threshold:\n"
            "            for i ran (0, 3):\n"
            "                if i == 1:\n"
            "                    continue\n"
            "                total += i\n"
            "        elif limit < threshold:\n"
            "            total -= 1\n"
            "        else:\n"
            "            pass\n"
            "        limit -= 1\n"
            "    return total\n"
        )
        storage = compile_snippet(code)
        self.assertIn('complex_algo', storage.functions)
        func = storage.functions['complex_algo']
        self.assertIsInstance(func, Function)
        self.assertEqual(func.return_type, 'int')

        # Inspeccionar jerarquía de sentencias en func.body
        self.assertGreaterEqual(len(func.body), 3)
        while_stmts = [s for s in func.body if isinstance(s, WhileStatement)]
        self.assertEqual(len(while_stmts), 1)
        w_stmt = while_stmts[0]

        if_stmts = [s for s in w_stmt.body if isinstance(s, IfStatement)]
        self.assertEqual(len(if_stmts), 1)
        if_stmt = if_stmts[0]

        self.assertEqual(len(if_stmt.elifs), 1)
        self.assertEqual(len(if_stmt.else_body), 1)

        for_stmts = [s for s in if_stmt.body if isinstance(s, ForStatement)]
        self.assertEqual(len(for_stmts), 1)
        for_stmt = for_stmts[0]
        self.assertEqual(for_stmt.mode, 'ran')

        inner_ifs = [s for s in for_stmt.body if isinstance(s, IfStatement)]
        self.assertEqual(len(inner_ifs), 1)

        # Verificar que el atributo scoped apunta a la función contenedora
        self.assertEqual(w_stmt.scoped, func)
        self.assertEqual(if_stmt.scoped, func)
        self.assertEqual(for_stmt.scoped, func)
        self.assertEqual(inner_ifs[0].scoped, func)

    def test_nested_if_in_all_branches(self):
        code = (
            "x: int = 1\n"
            "y: int = 2\n"
            "out: int = 0\n"
            "if x > 0:\n"
            "    if y > 0:\n"
            "        out = 10\n"
            "    else:\n"
            "        out = 11\n"
            "elif x < 0:\n"
            "    if y > 0:\n"
            "        out = 20\n"
            "    else:\n"
            "        out = 21\n"
            "else:\n"
            "    if y == 0:\n"
            "        out = 30\n"
            "    else:\n"
            "        out = 31\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        root_if = storage.statements[0]
        self.assertIsInstance(root_if, IfStatement)

        # Verificar nested if en rama principal
        nested_in_body = [s for s in root_if.body if isinstance(s, IfStatement)]
        self.assertEqual(len(nested_in_body), 1)

        # Verificar nested if en elif
        self.assertEqual(len(root_if.elifs), 1)
        nested_in_elif = [s for s in root_if.elifs[0].body if isinstance(s, IfStatement)]
        self.assertEqual(len(nested_in_elif), 1)

        # Verificar nested if en else
        nested_in_else = [s for s in root_if.else_body if isinstance(s, IfStatement)]
        self.assertEqual(len(nested_in_else), 1)

        # En el top-level global, scoped debe ser None
        self.assertIsNone(root_if.scoped)
        self.assertIsNone(nested_in_body[0].scoped)

    def test_compound_boolean_conditions(self):
        code = (
            "a: int = 10\n"
            "b: int = 20\n"
            "res: int = 0\n"
            "if a > 0 && b > 10:\n"
            "    res = 1\n"
            "elif a == 0 || b == 0:\n"
            "    res = 2\n"
            "while a > 0 && b > 0:\n"
            "    a -= 1\n"
            "    b -= 1\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 2)
        self.assertIsInstance(storage.statements[0], IfStatement)
        self.assertIsInstance(storage.statements[1], WhileStatement)

    def test_for_sequential_loops_in_same_scope(self):
        code = (
            "acc: int = 0\n"
            "for i ran 5:\n"
            "    acc += i\n"
            "for j ran 10:\n"
            "    acc += j\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 2)
        self.assertIn('i', storage.variables)
        self.assertIn('j', storage.variables)
        self.assertIsInstance(storage.statements[0], ForStatement)
        self.assertIsInstance(storage.statements[1], ForStatement)

    def test_void_function_with_early_returns_in_branches(self):
        code = (
            "void dispatch_action(code: int):\n"
            "    if code == 0:\n"
            "        return\n"
            "    elif code == 1:\n"
            "        return\n"
            "    else:\n"
            "        return\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['dispatch_action']
        self.assertEqual(func.return_type, 'void')
        self.assertEqual(len(func.body), 1)
        if_stmt = func.body[0]
        self.assertIsInstance(if_stmt, IfStatement)

    def test_multiple_break_continue_in_nested_loops(self):
        code = (
            "while true:\n"
            "    for i ran 10:\n"
            "        if i == 5:\n"
            "            break\n"
            "        elif i == 2:\n"
            "            continue\n"
            "    break\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        w = storage.statements[0]
        self.assertIsInstance(w, WhileStatement)

    def test_function_shadowing_global_variable(self):
        code = (
            "val: int = 999\n"
            "int get_val(val: int):\n"
            "    local_temp: int = val + 1\n"
            "    return local_temp\n"
        )
        storage = compile_snippet(code)
        self.assertIn('val', storage.variables)
        func = storage.functions['get_val']
        self.assertIn('val', func.scope.parameters)
        self.assertIn('local_temp', func.scope.variables)
        self.assertNotIn('local_temp', storage.variables)

    def test_for_ran_inside_while_inside_if(self):
        code = (
            "flag: int = 1\n"
            "result: int = 0\n"
            "if flag == 1:\n"
            "    w: int = 2\n"
            "    while w > 0:\n"
            "        for k ran 3:\n"
            "            result += k\n"
            "        w -= 1\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        top_if = storage.statements[0]
        self.assertIsInstance(top_if, IfStatement)

        # Buscar while dentro de if.body
        whiles = [s for s in top_if.body if isinstance(s, WhileStatement)]
        self.assertEqual(len(whiles), 1)
        w_stmt = whiles[0]

        # Buscar for dentro de while.body
        fors = [s for s in w_stmt.body if isinstance(s, ForStatement)]
        self.assertEqual(len(fors), 1)
        f_stmt = fors[0]
        self.assertEqual(f_stmt.targets, ['k'])

    def test_pass_only_bodies_across_all_constructs(self):
        code = (
            "void empty_flows():\n"
            "    if true:\n"
            "        pass\n"
            "    elif false:\n"
            "        pass\n"
            "    else:\n"
            "        pass\n"
            "    while false:\n"
            "        pass\n"
            "    for i ran 0:\n"
            "        pass\n"
            "    return\n"
        )
        storage = compile_snippet(code)
        func = storage.functions['empty_flows']
        self.assertEqual(len(func.body), 4)

    def test_reassignment_with_various_operators(self):
        code = (
            "val: int = 10\n"
            "while val > 0:\n"
            "    val -= 1\n"
            "    if val == 5:\n"
            "        val *= 2\n"
            "        val /= 2\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        w_stmt = storage.statements[0]
        self.assertIsInstance(w_stmt, WhileStatement)


if __name__ == '__main__':
    unittest.main()

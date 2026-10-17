import unittest
from test.helpers import compile_snippet
from core.processor.objects.for_statement import ForStatement
from core.processor.objects.while_statement import WhileStatement


class TestForStatement(unittest.TestCase):
    def test_basic_for_ran(self):
        code = (
            "for i ran (0, 10):\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        for_stmt = storage.statements[0]
        self.assertIsInstance(for_stmt, ForStatement)
        self.assertEqual(for_stmt.mode, 'ran')
        self.assertEqual(for_stmt.targets, ['i'])
        self.assertIn('i', storage.variables)
        self.assertEqual(storage.variables['i'].type, 'int')

    def test_for_ran_with_assignation(self):
        code = (
            "total: int = 0\n"
            "for i ran (0, 5):\n"
            "    total += i\n"
        )
        storage = compile_snippet(code)
        self.assertIn('total', storage.variables)
        self.assertEqual(len(storage.statements), 1)
        for_stmt = storage.statements[0]
        self.assertIsInstance(for_stmt, ForStatement)
        self.assertEqual(len(for_stmt.body), 1)

    def test_for_in_string_collection(self):
        code = (
            "text: chain = \"hello\"\n"
            "for ch in text:\n"
            "    pass\n"
        )

        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        for_stmt = storage.statements[0]
        self.assertEqual(for_stmt.mode, 'in')
        self.assertEqual(for_stmt.targets, ['ch'])
        self.assertIn('ch', storage.variables)
        self.assertEqual(storage.variables['ch'].type, 'char')

    def test_for_with_break_and_continue(self):
        code = (
            "for i ran (0, 10):\n"
            "    break\n"
            "for i ran (0, 10):\n"
            "    continue\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 2)
        f1 = storage.statements[0]
        f2 = storage.statements[1]
        self.assertIsInstance(f1, ForStatement)
        self.assertIsInstance(f2, ForStatement)

    def test_nested_for_loops(self):
        code = (
            "count: int = 0\n"
            "for i ran (0, 3):\n"
            "    for j ran (0, 3):\n"
            "        count += 1\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        outer_for = storage.statements[0]
        self.assertIsInstance(outer_for, ForStatement)

        # Encontrar el bucle interno en outer_for.body
        nested_fors = [stmt for stmt in outer_for.body if isinstance(stmt, ForStatement)]
        self.assertEqual(len(nested_fors), 1)
        inner_for = nested_fors[0]
        self.assertIsInstance(inner_for, ForStatement)
        self.assertEqual(inner_for.targets, ['j'])

    def test_for_inside_function(self):
        code = (
            "int calculate_sum(limit: int):\n"
            "    acc: int = 0\n"
            "    for k ran (0, limit):\n"
            "        acc += k\n"
            "    return acc\n"
        )
        storage = compile_snippet(code)
        self.assertIn('calculate_sum', storage.functions)
        func = storage.functions['calculate_sum']

        # Encontrar ForStatement en func.body
        for_stmts = [stmt for stmt in func.body if isinstance(stmt, ForStatement)]
        self.assertEqual(len(for_stmts), 1)
        for_stmt = for_stmts[0]
        self.assertIsInstance(for_stmt, ForStatement)

        # Variables locales de la función
        self.assertIn('acc', func.scope.variables)
        self.assertIn('k', func.scope.variables)
        # No deben existir en el almacenamiento global
        self.assertNotIn('k', storage.variables)
        self.assertNotIn('acc', storage.variables)

    def test_for_nested_with_while(self):
        code = (
            "x: int = 0\n"
            "for i ran (0, 3):\n"
            "    while x < 5:\n"
            "        x += 1\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        outer_for = storage.statements[0]
        self.assertIsInstance(outer_for, ForStatement)

        # Verificar WhileStatement dentro de ForStatement
        nested_whiles = [stmt for stmt in outer_for.body if isinstance(stmt, WhileStatement)]
        self.assertEqual(len(nested_whiles), 1)
        while_stmt = nested_whiles[0]
        self.assertIsInstance(while_stmt, WhileStatement)

    def test_for_ran_bare_number(self):
        code = (
            "for i ran 100:\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        for_stmt = storage.statements[0]
        self.assertIsInstance(for_stmt, ForStatement)
        self.assertEqual(for_stmt.mode, 'ran')
        self.assertEqual(for_stmt.targets, ['i'])
        self.assertIn('i', storage.variables)
        self.assertEqual(storage.variables['i'].type, 'int')

    def test_for_ran_single_arg_parens(self):
        code = (
            "for i ran(100):\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        for_stmt = storage.statements[0]
        self.assertIsInstance(for_stmt, ForStatement)
        self.assertEqual(for_stmt.mode, 'ran')
        self.assertEqual(for_stmt.targets, ['i'])
        self.assertIn('i', storage.variables)

    def test_for_ran_three_args(self):
        code = (
            "for i ran(1, 100, 2):\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(len(storage.statements), 1)
        for_stmt = storage.statements[0]
        self.assertIsInstance(for_stmt, ForStatement)
        self.assertEqual(for_stmt.mode, 'ran')
        self.assertEqual(for_stmt.targets, ['i'])


if __name__ == '__main__':
    unittest.main()

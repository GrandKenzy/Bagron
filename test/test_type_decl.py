import unittest
from test.helpers import parse_snippet, compile_snippet
from core.processor.objects.type_decl import TypeAlias


class TestTypeDecl(unittest.TestCase):
    def test_basic_typealias(self):
        code = "TypeAlias int MiEntero\n"
        ast = parse_snippet(code)
        self.assertEqual(len(ast), 1)
        node = ast[0]
        self.assertEqual(node.name, 'TYPEALIAS')
        self.assertEqual(len(node.nodes), 3)
        self.assertEqual(node.nodes[0].token.value, 'TypeAlias')
        self.assertEqual(node.nodes[1].name, 'SEGMENT_TYPE')
        self.assertEqual(node.nodes[1].nodes[0].token.value, 'int')
        self.assertEqual(node.nodes[2].token.value, 'MiEntero')

    def test_public_typealias(self):
        code = "public TypeAlias int MiEntero\n"
        ast = parse_snippet(code)
        self.assertEqual(len(ast), 1)
        node = ast[0]
        self.assertEqual(node.name, 'TYPEALIAS')
        self.assertEqual(len(node.nodes), 4)
        self.assertEqual(node.nodes[0].token.value, 'public')
        self.assertEqual(node.nodes[1].token.value, 'TypeAlias')
        self.assertEqual(node.nodes[2].name, 'SEGMENT_TYPE')
        self.assertEqual(node.nodes[2].nodes[0].token.value, 'int')
        self.assertEqual(node.nodes[3].token.value, 'MiEntero')

    def test_private_typealias(self):
        code = "private TypeAlias float MiFlotante\n"
        ast = parse_snippet(code)
        self.assertEqual(len(ast), 1)
        node = ast[0]
        self.assertEqual(node.name, 'TYPEALIAS')
        self.assertEqual(len(node.nodes), 4)
        self.assertEqual(node.nodes[0].token.value, 'private')
        self.assertEqual(node.nodes[1].token.value, 'TypeAlias')
        self.assertEqual(node.nodes[2].name, 'SEGMENT_TYPE')
        self.assertEqual(node.nodes[2].nodes[0].token.value, 'float')
        self.assertEqual(node.nodes[3].token.value, 'MiFlotante')

    def test_typealias_with_array(self):
        code = "TypeAlias array[int, 10] Buffer\n"
        ast = parse_snippet(code)
        self.assertEqual(len(ast), 1)
        node = ast[0]
        self.assertEqual(node.name, 'TYPEALIAS')
        self.assertEqual(node.nodes[0].token.value, 'TypeAlias')
        self.assertEqual(node.nodes[1].name, 'SEGMENT_TYPE')
        self.assertEqual(node.nodes[1].nodes[0].name, 'ARRAY')
        self.assertEqual(node.nodes[2].token.value, 'Buffer')

    def test_typealias_with_custom_ident(self):
        code = "TypeAlias Point Vector2D\n"
        ast = parse_snippet(code)
        self.assertEqual(len(ast), 1)
        node = ast[0]
        self.assertEqual(node.name, 'TYPEALIAS')
        self.assertEqual(node.nodes[0].token.value, 'TypeAlias')
        self.assertEqual(node.nodes[1].nodes[0].token.value, 'Point')
        self.assertEqual(node.nodes[2].token.value, 'Vector2D')

    def test_semantic_typealias_registration(self):
        code = "TypeAlias int MiEntero\n"
        storage = compile_snippet(code)
        self.assertIn('MiEntero', storage.types)
        alias = storage.types['MiEntero']
        self.assertIsInstance(alias, TypeAlias)
        self.assertEqual(alias.name, 'MiEntero')
        self.assertEqual(alias.target_type, 'int')
        self.assertEqual(alias.privacy, 'public')
        self.assertEqual(storage.resolve_type('MiEntero'), 'int')

    def test_semantic_typealias_privacy_modifiers(self):
        code = (
            "public TypeAlias int Contador\n"
            "private TypeAlias float Medida\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.types['Contador'].privacy, 'public')
        self.assertEqual(storage.types['Medida'].privacy, 'private')

    def test_semantic_typealias_inherited_privacy(self):
        code = (
            "clause Visibility 'private'\n"
            "TypeAlias int SecretID\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.types['SecretID'].privacy, 'private')

    def test_semantic_typealias_collision_with_existing_variable(self):
        code = (
            "x: int = 10\n"
            "TypeAlias float x\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_semantic_typealias_collision_with_another_alias(self):
        code = (
            "TypeAlias int MiTipo\n"
            "TypeAlias chain MiTipo\n"
        )

        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_semantic_typealias_in_var_decl_and_validation(self):
        code = (
            "TypeAlias int MiEntero\n"
            "edad: MiEntero = 30\n"
        )
        storage = compile_snippet(code)
        self.assertIn('edad', storage.variables)
        self.assertEqual(storage.variables['edad'].type, 'MiEntero')

        # Con error de tipo
        bad_code = (
            "TypeAlias int MiEntero\n"
            "edad: MiEntero = 'treinta'\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(bad_code)

    def test_semantic_chained_typealias(self):
        code = (
            "TypeAlias int BaseInt\n"
            "TypeAlias BaseInt AliasInt\n"
            "val: AliasInt = 123\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.resolve_type('AliasInt'), 'int')
        self.assertIn('val', storage.variables)

    def test_semantic_typealias_in_function(self):
        code = (
            "TypeAlias int MiEntero\n"
            "MiEntero duplicar(x: MiEntero):\n"
            "    return x * 2\n"
        )
        storage = compile_snippet(code)
        self.assertIn('duplicar', storage.functions)
        func = storage.functions['duplicar']
        self.assertEqual(func.return_type, 'MiEntero')
        self.assertEqual(func.parameters[0].type, 'MiEntero')


if __name__ == '__main__':
    unittest.main()

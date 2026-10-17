import unittest
from pathlib import Path
from core.compiler import compile as compile_project


class TestImportsIncludes(unittest.TestCase):
    def test_compile_modern_example(self):
        example_dir = Path("examples/modern_example").resolve()
        storage = compile_project(example_dir)

        # Verificar include
        self.assertIn('stdlib', storage.includes)

        # Verificar import y compilación de módulo
        self.assertIn('standard', storage.modules)
        module_storage = storage.modules['standard']
        self.assertIsNotNone(module_storage)

        # Verificar variables
        self.assertIn('a', storage.variables)
        self.assertEqual(storage.variables['a'].type, 'int')


if __name__ == '__main__':
    unittest.main()

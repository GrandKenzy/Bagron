import unittest
from core.processor import magic_methods as mm


class TestMagicMethods(unittest.TestCase):
    def test_catalog_completeness(self):
        """Verifica que el catálogo contenga todos los métodos mágicos esperados (55 métodos)."""
        self.assertEqual(len(mm.MAGIC_METHODS), 55)

    def test_all_defaults_are_strictly_void_or_zero(self):
        """Garantía de diseño de Easy-C: cuando no se declaran, SIEMPRE retornan 'void' o '0'."""
        for name, spec in mm.MAGIC_METHODS.items():
            self.assertIn(
                spec.default_return_type,
                ('void', 'int'),
                f"El método '{name}' tiene tipo de retorno inválido: {spec.default_return_type}",
            )
            self.assertIn(
                spec.default_return_value,
                ('void', '0'),
                f"El método '{name}' tiene valor por defecto inválido: {spec.default_return_value}",
            )

    def test_is_magic_method(self):
        self.assertTrue(mm.is_magic_method('__init__'))
        self.assertTrue(mm.is_magic_method('__new__'))
        self.assertTrue(mm.is_magic_method('__add__'))
        self.assertTrue(mm.is_magic_method('__len__'))
        self.assertTrue(mm.is_magic_method('__getitem__'))
        self.assertTrue(mm.is_magic_method('__setitem__'))
        self.assertFalse(mm.is_magic_method('foo'))
        self.assertFalse(mm.is_magic_method('bar'))
        self.assertFalse(mm.is_magic_method('_private'))

    def test_get_default_return(self):
        # Métodos con default void
        self.assertEqual(mm.get_default_return('__init__'), ('void', 'void'))
        self.assertEqual(mm.get_default_return('__del__'), ('void', 'void'))
        self.assertEqual(mm.get_default_return('__setitem__'), ('void', 'void'))
        self.assertEqual(mm.get_default_return('__iadd__'), ('void', 'void'))
        self.assertEqual(mm.get_default_return('__call__'), ('void', 'void'))

        # Métodos con default 0
        self.assertEqual(mm.get_default_return('__add__'), ('int', '0'))
        self.assertEqual(mm.get_default_return('__sub__'), ('int', '0'))
        self.assertEqual(mm.get_default_return('__eq__'), ('int', '0'))
        self.assertEqual(mm.get_default_return('__ne__'), ('int', '0'))
        self.assertEqual(mm.get_default_return('__len__'), ('int', '0'))
        self.assertEqual(mm.get_default_return('__bool__'), ('int', '0'))
        self.assertEqual(mm.get_default_return('__getitem__'), ('int', '0'))
        self.assertEqual(mm.get_default_return('__iter__'), ('int', '0'))

    def test_get_operator_magic(self):
        add_spec = mm.get_operator_magic('+')
        self.assertIsNotNone(add_spec)
        self.assertEqual(add_spec.name, '__add__')

        iadd_spec = mm.get_operator_magic('+=')
        self.assertIsNotNone(iadd_spec)
        self.assertEqual(iadd_spec.name, '__iadd__')

        eq_spec = mm.get_operator_magic('==')
        self.assertIsNotNone(eq_spec)
        self.assertEqual(eq_spec.name, '__eq__')

        get_spec = mm.get_operator_magic('[]')
        self.assertIsNotNone(get_spec)
        self.assertEqual(get_spec.name, '__getitem__')

        set_spec = mm.get_operator_magic('[]=')
        self.assertIsNotNone(set_spec)
        self.assertEqual(set_spec.name, '__setitem__')

    def test_partition_void_and_zero(self):
        voids = set(mm.get_void_defaults())
        zeros = set(mm.get_zero_defaults())

        self.assertEqual(len(voids) + len(zeros), len(mm.MAGIC_METHODS))
        self.assertTrue(voids.isdisjoint(zeros))
        self.assertIn('__init__', voids)
        self.assertIn('__del__', voids)
        self.assertIn('__iadd__', voids)
        self.assertIn('__add__', zeros)
        self.assertIn('__eq__', zeros)
        self.assertIn('__len__', zeros)


if __name__ == '__main__':
    unittest.main()

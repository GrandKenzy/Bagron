import unittest
from test.helpers import compile_snippet
from core.processor.objects.class_decl import ClassDecl, ClassMethod


class TestClassDecl(unittest.TestCase):
    # ==========================================
    # 1. Declaración básica y métodos mágicos
    # ==========================================
    def test_basic_class_declaration(self):
        code = (
            "class Persona:\n"
            "    edad: int = 30\n"
        )
        storage = compile_snippet(code)
        self.assertIn('Persona', storage.classes)
        cls_obj = storage.classes['Persona']
        self.assertIsInstance(cls_obj, ClassDecl)
        self.assertEqual(cls_obj.name, 'Persona')
        self.assertIn('edad', cls_obj.class_fields)
        self.assertEqual(cls_obj.class_fields['edad'].type, 'int')
        # __new__ y __init__ se auto-generan
        self.assertIsNotNone(cls_obj.new_method)
        self.assertIsNotNone(cls_obj.init_method)
        self.assertEqual(cls_obj.new_method.return_type, 'void')
        self.assertEqual(cls_obj.init_method.return_type, 'void')

    def test_explicit_new_and_init_returning_void(self):
        code = (
            "class Motor:\n"
            "    void __new__():\n"
            "        pass\n"
            "    void __init__():\n"
            "        pass\n"
        )
        storage = compile_snippet(code)
        cls_obj = storage.classes['Motor']
        self.assertEqual(cls_obj.new_method.return_type, 'void')
        self.assertEqual(cls_obj.init_method.return_type, 'void')

    def test_init_returning_non_void_raises_type_error(self):
        code = (
            "class Invalido:\n"
            "    int __init__():\n"
            "        return 1\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_new_returning_non_void_raises_type_error(self):
        code = (
            "class Invalido:\n"
            "    int __new__():\n"
            "        return 1\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_direct_call_to_magic_method_raises_runtime_error(self):
        code = (
            "class Test:\n"
            "    void __init__():\n"
            "        pass\n"
            "t: Test = Test()\n"
            "t.__init__()\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_direct_call_to_new_raises_runtime_error(self):
        code = (
            "class Test:\n"
            "    pass\n"
            "Test.__new__()\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    # ==========================================
    # 2. Instanciación y argumentos
    # ==========================================
    def test_instantiation_without_params(self):
        code = (
            "class Empty:\n"
            "    pass\n"
            "e: Empty = Empty()\n"
        )
        storage = compile_snippet(code)
        self.assertIn('e', storage.variables)
        self.assertEqual(storage.variables['e'].type, 'Empty')

    def test_instantiation_with_params(self):
        code = (
            "class Point:\n"
            "    void __init__(x: int, y: int):\n"
            "        self.x = x\n"
            "        self.y = y\n"
            "p: Point = Point(10, 20)\n"
        )
        storage = compile_snippet(code)
        self.assertIn('p', storage.variables)
        self.assertEqual(storage.variables['p'].type, 'Point')
        cls_obj = storage.classes['Point']
        self.assertIn('x', cls_obj.instance_fields)
        self.assertIn('y', cls_obj.instance_fields)
        self.assertEqual(cls_obj.instance_fields['x'].type, 'int')

    def test_instantiation_arg_count_mismatch(self):
        code = (
            "class Point:\n"
            "    void __init__(x: int, y: int):\n"
            "        pass\n"
            "p: Point = Point(10)\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_instantiation_arg_type_mismatch(self):
        code = (
            "class Point:\n"
            "    void __init__(x: int, y: int):\n"
            "        pass\n"
            "p: Point = Point(10, \"hola\")\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    # ==========================================
    # 3. Métodos de instancia, de clase y estáticos
    # ==========================================
    def test_instance_method_call(self):
        code = (
            "class Calculadora:\n"
            "    valor: int = 0\n"
            "    void __init__(init_val: int):\n"
            "        self.val = init_val\n"
            "    int get_val():\n"
            "        return self.val\n"
            "calc: Calculadora = Calculadora(42)\n"
            "res: int = calc.get_val()\n"
        )
        storage = compile_snippet(code)
        self.assertIn('res', storage.variables)
        self.assertEqual(storage.variables['res'].type, 'int')

    def test_instance_method_called_from_class_raises_error(self):
        code = (
            "class Foo:\n"
            "    void bar():\n"
            "        pass\n"
            "Foo.bar()\n"
        )
        with self.assertRaises(AttributeError):
            compile_snippet(code)

    def test_classmethod_called_from_class(self):
        code = (
            "class Factory:\n"
            "    count: int = 0\n"
            "    @classmethod\n"
            "    int get_count():\n"
            "        return cls.count\n"
            "total: int = Factory.get_count()\n"
        )
        storage = compile_snippet(code)
        self.assertIn('total', storage.variables)
        self.assertEqual(storage.variables['total'].type, 'int')

    def test_classmethod_called_from_instance_raises_error(self):
        code = (
            "class Factory:\n"
            "    @classmethod\n"
            "    void reset():\n"
            "        pass\n"
            "f: Factory = Factory()\n"
            "f.reset()\n"
        )
        with self.assertRaises(AttributeError):
            compile_snippet(code)

    def test_staticmethod_called_from_class(self):
        code = (
            "class MathHelper:\n"
            "    @staticmethod\n"
            "    int add(a: int, b: int):\n"
            "        return a + b\n"
            "sum: int = MathHelper.add(5, 3)\n"
        )
        storage = compile_snippet(code)
        self.assertIn('sum', storage.variables)
        self.assertEqual(storage.variables['sum'].type, 'int')

    def test_staticmethod_called_from_instance_raises_error(self):
        code = (
            "class MathHelper:\n"
            "    @staticmethod\n"
            "    int add(a: int, b: int):\n"
            "        return a + b\n"
            "m: MathHelper = MathHelper()\n"
            "res: int = m.add(1, 2)\n"
        )
        with self.assertRaises(AttributeError):
            compile_snippet(code)

    def test_staticmethod_using_self_raises_error(self):
        code = (
            "class Invalido:\n"
            "    @staticmethod\n"
            "    void bad():\n"
            "        self.x = 10\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_staticmethod_using_cls_raises_error(self):
        code = (
            "class Invalido:\n"
            "    @staticmethod\n"
            "    void bad():\n"
            "        cls.x = 10\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    # ==========================================
    # 4. Inmutabilidad y prohibición de monkey-patching
    # ==========================================
    def test_no_monkey_patching_instance_outside_init(self):
        code = (
            "class Data:\n"
            "    void __init__():\n"
            "        self.a = 1\n"
            "    void set_b():\n"
            "        self.b = 2\n"
        )
        with self.assertRaises(AttributeError):
            compile_snippet(code)

    def test_no_monkey_patching_instance_external(self):
        code = (
            "class Data:\n"
            "    void __init__():\n"
            "        self.a = 1\n"
            "d: Data = Data()\n"
            "d.extra = 99\n"
        )
        with self.assertRaises(AttributeError):
            compile_snippet(code)

    def test_no_monkey_patching_class_external(self):
        code = (
            "class Data:\n"
            "    existing: int = 10\n"
            "Data.nuevo = 20\n"
        )
        with self.assertRaises(AttributeError):
            compile_snippet(code)

    def test_valid_mutation_of_declared_attributes(self):
        code = (
            "class Data:\n"
            "    static_val: int = 10\n"
            "    void __init__():\n"
            "        self.inst_val = 20\n"
            "Data.static_val = 15\n"
            "d: Data = Data()\n"
            "d.inst_val = 25\n"
        )
        storage = compile_snippet(code)
        self.assertIn('d', storage.variables)
        self.assertEqual(storage.variables['d'].type, 'Data')
        self.assertEqual(storage.variables['d'].uses, 1)
        self.assertIn('static_val', storage.classes['Data'].class_fields)
        self.assertIn('inst_val', storage.classes['Data'].instance_fields)

    # ==========================================
    # 5. Punteros self y cls, identificadores reservados
    # ==========================================
    def test_self_reassignment_raises_error(self):
        code = (
            "class Foo:\n"
            "    void bar():\n"
            "        self = 10\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_cls_reassignment_raises_error(self):
        code = (
            "class Foo:\n"
            "    @classmethod\n"
            "    void bar():\n"
            "        cls = 10\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_reserved_name_variable_raises_error(self):
        code = (
            "self: int = 10\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_reserved_name_function_raises_error(self):
        code = (
            "void self():\n"
            "    pass\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_reserved_name_parameter_raises_error(self):
        code = (
            "void test_func(self: int):\n"
            "    pass\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_self_in_new_acts_as_cls(self):
        code = (
            "class Singleton:\n"
            "    count: int = 0\n"
            "    @classmethod\n"
            "    void helper():\n"
            "        pass\n"
            "    void __new__():\n"
            "        self.created: int = 1\n"
            "        self.helper()\n"
        )
        storage = compile_snippet(code)
        cls_obj = storage.classes['Singleton']
        self.assertIn('created', cls_obj.class_fields)
        self.assertEqual(cls_obj.class_fields['created'].type, 'int')

    def test_instance_cannot_access_class_field_directly(self):
        code = (
            "class Config:\n"
            "    timeout: int = 5000\n"
            "cfg: Config = Config()\n"
            "t: int = cfg.timeout\n"
        )
        with self.assertRaises(AttributeError):
            compile_snippet(code)

    def test_class_cannot_access_instance_field_directly(self):
        code = (
            "class Config:\n"
            "    void __init__():\n"
            "        self.user = \"admin\"\n"
            "u: chain = Config.user\n"
        )

        with self.assertRaises(AttributeError):
            compile_snippet(code)

    def test_class_privacy_modifiers(self):
        code = (
            "private class InternalClass:\n"
            "    pass\n"
        )
        storage = compile_snippet(code)
        self.assertEqual(storage.classes['InternalClass'].privacy, 'private')

    def test_duplicate_method_name_raises_error(self):
        code = (
            "class Dup:\n"
            "    void m():\n"
            "        pass\n"
            "    void m():\n"
            "        pass\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    def test_duplicate_field_name_raises_error(self):
        code = (
            "class Dup:\n"
            "    a: int = 1\n"
            "    a: int = 2\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    # ========================================================
    # CAL-03: Herencia recursiva y resolución de métodos/símbolos
    # ========================================================
    def test_inheritance_inherits_methods_and_fields(self):
        code = (
            "class Animal:\n"
            "    species_id: int = 1\n"
            "    void __init__():\n"
            "        self.age = 0\n"
            "    void sleep():\n"
            "        pass\n"
            "class Dog(Animal):\n"
            "    void bark():\n"
            "        pass\n"
        )
        storage = compile_snippet(code)
        dog = storage.classes['Dog']
        self.assertIn('species_id', dog.class_fields)
        self.assertIn('age', dog.instance_fields)
        self.assertIn('sleep', dog.instance_methods)
        self.assertIn('bark', dog.instance_methods)

    def test_inheritance_method_override_and_call(self):
        code = (
            "class Animal:\n"
            "    void speak():\n"
            "        pass\n"
            "class Cat(Animal):\n"
            "    void speak():\n"
            "        pass\n"
            "c: Cat = Cat()\n"
            "c.speak()\n"
        )
        storage = compile_snippet(code)
        cat = storage.classes['Cat']
        self.assertIn('speak', cat.instance_methods)
        self.assertEqual(len(storage.statements), 1)

    def test_recursive_inheritance_multilevel(self):
        code = (
            "class Organism:\n"
            "    living: int = 1\n"
            "    void respire():\n"
            "        pass\n"
            "class Animal(Organism):\n"
            "    void move():\n"
            "        pass\n"
            "class Dog(Animal):\n"
            "    void bark():\n"
            "        pass\n"
        )
        storage = compile_snippet(code)
        dog = storage.classes['Dog']
        self.assertIn('living', dog.class_fields)
        self.assertIn('respire', dog.instance_methods)
        self.assertIn('move', dog.instance_methods)
        self.assertIn('bark', dog.instance_methods)

    def test_inheritance_cycle_raises_error(self):
        code = (
            "class A(B):\n"
            "    pass\n"
            "class B(A):\n"
            "    pass\n"
        )
        with self.assertRaises(RuntimeError):
            compile_snippet(code)

    # ========================================================
    # CLS-02: super().__init__() y Unión de Clases
    # ========================================================
    def test_super_init_unites_classes(self):
        code = (
            "class Animal:\n"
            "    void __init__():\n"
            "        self.age = 0\n"
            "class Dog(Animal):\n"
            "    void __init__():\n"
            "        super().__init__()\n"
            "        self.breed = 'Labrador'\n"
        )
        storage = compile_snippet(code)
        dog = storage.classes['Dog']
        self.assertIn('age', dog.instance_fields)
        self.assertIn('breed', dog.instance_fields)
        self.assertEqual(dog.instance_fields['age'].type, 'int')
        self.assertEqual(dog.instance_fields['breed'].type, 'chain')

    def test_subclass_without_super_init_does_not_unite_base_fields(self):
        code = (
            "class Animal:\n"
            "    void __init__():\n"
            "        self.age = 0\n"
            "class Cat(Animal):\n"
            "    void __init__():\n"
            "        self.color = 'black'\n"
        )
        storage = compile_snippet(code)
        cat = storage.classes['Cat']
        self.assertIn('color', cat.instance_fields)
        self.assertNotIn('age', cat.instance_fields)

    def test_super_init_with_arguments(self):
        code = (
            "class Vehicle:\n"
            "    void __init__(wheels: int):\n"
            "        self.wheels = wheels\n"
            "class Car(Vehicle):\n"
            "    void __init__(wheels: int, doors: int):\n"
            "        super().__init__(wheels)\n"
            "        self.doors = doors\n"
        )
        storage = compile_snippet(code)
        car = storage.classes['Car']
        self.assertIn('wheels', car.instance_fields)
        self.assertIn('doors', car.instance_fields)

    def test_super_init_with_wrong_argument_type_raises_type_error(self):
        code = (
            "class Vehicle:\n"
            "    void __init__(wheels: int):\n"
            "        self.wheels = wheels\n"
            "class Car(Vehicle):\n"
            "    void __init__():\n"
            "        super().__init__('cuatro')\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_super_init_with_insufficient_arguments_raises_type_error(self):
        code = (
            "class Vehicle:\n"
            "    void __init__(wheels: int):\n"
            "        self.wheels = wheels\n"
            "class Car(Vehicle):\n"
            "    void __init__():\n"
            "        super().__init__()\n"
        )
        with self.assertRaises(TypeError):
            compile_snippet(code)

    def test_super_method_raises_runtime_error(self):
        code = (
            "class Animal:\n"
            "    void sleep():\n"
            "        pass\n"
            "class Dog(Animal):\n"
            "    void bark():\n"
            "        super().sleep()\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("No se permite 'super().sleep()'", str(ctx.exception))
        self.assertIn("unión de clases", str(ctx.exception))

    def test_super_field_access_raises_runtime_error(self):
        code = (
            "class Animal:\n"
            "    species: int = 1\n"
            "class Dog(Animal):\n"
            "    void bark():\n"
            "        s: int = super.species\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("No se permite acceso a miembro 'super.species'", str(ctx.exception))

    def test_super_isolated_raises_runtime_error(self):
        code = (
            "class Animal:\n"
            "    void __init__():\n"
            "        super()\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("'super()' no puede usarse de forma aislada", str(ctx.exception))

    def test_super_outside_init_raises_runtime_error(self):
        code = (
            "class Animal:\n"
            "    void __init__():\n"
            "        pass\n"
            "class Dog(Animal):\n"
            "    void bark():\n"
            "        super().__init__()\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("'super().__init__()' solo puede invocarse dentro del método '__init__'", str(ctx.exception))

    def test_super_in_class_without_base_raises_runtime_error(self):
        code = (
            "class Solo:\n"
            "    void __init__():\n"
            "        super().__init__()\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("no hereda de ninguna clase base", str(ctx.exception))

    def test_duplicate_super_init_raises_runtime_error(self):
        code = (
            "class Animal:\n"
            "    void __init__():\n"
            "        pass\n"
            "class Dog(Animal):\n"
            "    void __init__():\n"
            "        super().__init__()\n"
            "        super().__init__()\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            compile_snippet(code)
        self.assertIn("Llamada duplicada a 'super().__init__()'", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()

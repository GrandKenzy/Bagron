from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class ClassAndNeverTests(unittest.TestCase):
    """Dedicated stress coverage for class semantics and the Never type."""

    def compile_source(self, source: str, *, executable: bool = False):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        return Compiler().compile(path, executable=executable)

    def compile_module(self, source: str) -> str:
        output = self.compile_source(source, executable=False)
        return Path(output).read_text(encoding='utf-8')

    def compile_compiler(self, source: str) -> Compiler:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        compiler = Compiler()
        compiler.compile(path, executable=False)
        return compiler

    def run_source(self, source: str) -> subprocess.CompletedProcess[str]:
        artifacts = self.compile_source(source, executable=True)
        return subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
            text=True,
        )

    def assert_compile_error(self, source: str, pattern: str) -> None:
        with self.assertRaisesRegex(CompilationError, pattern):
            self.compile_source(source)

    def test_class_init_methods_and_hidden_receiver(self):
        result = self.run_source(
            'class Point:\n'
            '    func __init__(x: int32, y: int32) void:\n'
            '        self.x = x\n'
            '        self.y = y\n'
            '    func total() int32:\n'
            '        return self.x + self.y\n'
            '    func add(value: int32) int32:\n'
            '        self.x += value\n'
            '        return self.total()\n'
            'func main() int32:\n'
            '    point: Point = Point(4, 3)\n'
            '    first: int32 = point.add(2)\n'
            '    second: int32 = point.total()\n'
            '    return first + second\n'
        )
        self.assertEqual(18, result.returncode)

    def test_instance_receiver_is_hidden_from_source_signature(self):
        source = (
            'class Box:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func get() int32:\n'
            '        return self.value\n'
            'func main() int32:\n'
            '    box: Box = Box(4)\n'
            '    return box.get()\n'
        )
        compiler = self.compile_compiler(source)
        method = compiler.storage.methods[('Box', 'get')]
        self.assertTrue(method.signature.parameters[0].is_receiver)
        self.assertEqual('__self', method.signature.parameters[0].name)

    def test_static_method_is_called_through_class_only(self):
        result = self.run_source(
            'class Math:\n'
            '    pass\n'
            '    @static\n'
            '    func add(left: int32, right: int32) int32:\n'
            '        return left + right\n'
            'func main() int32:\n'
            '    return Math.add(4, 5)\n'
        )
        self.assertEqual(9, result.returncode)

    def test_instance_method_cannot_be_called_through_class(self):
        self.assert_compile_error(
            'class Box:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func get() int32:\n'
            '        return self.value\n'
            'func main() int32:\n'
            '    return Box.get()\n',
            'requiere una instancia',
        )

    def test_static_method_cannot_be_called_through_instance(self):
        self.assert_compile_error(
            'class Box:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    @static\n'
            '    func answer() int32:\n'
            '        return 42\n'
            'func main() int32:\n'
            '    box: Box = Box(1)\n'
            '    return box.answer()\n',
            'metodo estatico.*debe llamarse',
        )

    def test_frozen_allows_initialization_but_rejects_method_writes(self):
        self.assert_compile_error(
            '@frozen\n'
            'class Box:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func mutate() void:\n'
            '        self.value = 2\n'
            '        return\n'
            'func main() int32:\n'
            '    box: Box = Box(1)\n'
            '    return 0\n',
            'clase @frozen Box.*no permite modificar',
        )

    def test_frozen_rejects_external_and_compound_writes(self):
        self.assert_compile_error(
            '@frozen\n'
            'class Box:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            'func main() int32:\n'
            '    box: Box = Box(1)\n'
            '    box.value += 1\n'
            '    return 0\n',
            'clase @frozen Box.*no permite modificar',
        )

    def test_frozen_blocks_known_pointer_aliases(self):
        self.assert_compile_error(
            '@frozen\n'
            'class Box:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '@unsafe\n'
            'func mutate(box: Box) void:\n'
            '    pointer *: int32 = $box.value\n'
            '    (pointer) = 2\n'
            '    return\n'
            'func main() int32:\n'
            '    return 0\n',
            'clase @frozen Box.*no permite modificar',
        )

    def test_frozen_inheritance_must_match_parent_state(self):
        self.assert_compile_error(
            '@frozen\n'
            'class Base:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            'class Child(Base):\n'
            '    func __init__(value: int32) void:\n'
            '        super.__init__(value)\n'
            'func main() int32:\n'
            '    return 0\n',
            'hereda de la clase @frozen.*tambien debe ser @frozen',
        )
        self.assert_compile_error(
            'class Base:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '@frozen\n'
            'class Child(Base):\n'
            '    func __init__(value: int32) void:\n'
            '        super.__init__(value)\n'
            'func main() int32:\n'
            '    return 0\n',
            'clase @frozen Child.*solo puede heredar',
        )

    def test_frozen_is_shallow_for_mutable_nested_classes(self):
        result = self.run_source(
            'class Inner:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '@frozen\n'
            'class Outer:\n'
            '    func __init__(value: int32) void:\n'
            '        self.inner = Inner(value)\n'
            'func main() int32:\n'
            '    outer: Outer = Outer(1)\n'
            '    outer.inner.value = 4\n'
            '    return outer.inner.value\n'
        )
        self.assertEqual(4, result.returncode)

    def test_frozen_rejects_unknown_and_duplicate_class_decorators(self):
        self.assert_compile_error(
            '@mystery\n'
            'class Box:\n'
            '    pass\n'
            'func main() int32:\n'
            '    return 0\n',
            'decorador @mystery.*clase Box',
        )
        self.assert_compile_error(
            '@frozen\n'
            '@frozen\n'
            'class Box:\n'
            '    pass\n'
            'func main() int32:\n'
            '    return 0\n',
            'decorador @frozen esta repetido.*clase Box',
        )

    def test_frontend_initializer_converts_source_value(self):
        result = self.run_source(
            'class Text:\n'
            '    func __frontend__(value: chain) void:\n'
            '        self.marker = 11\n'
            '    func marker_value() int32:\n'
            '        return self.marker\n'
            'func main() int32:\n'
            '    text: Text = "Hola"\n'
            '    return text.marker_value()\n'
        )
        self.assertEqual(11, result.returncode)

    def test_class_cannot_have_two_initializers(self):
        self.assert_compile_error(
            'class Broken:\n'
            '    func __init__() void:\n'
            '        pass\n'
            '    func __frontend__(value: chain) void:\n'
            '        pass\n'
            'func main() int32:\n'
            '    return 0\n',
            'solo puede especificar un iniciador',
        )

    def test_class_without_initializer_cannot_be_constructed(self):
        self.assert_compile_error(
            'class Empty:\n'
            '    pass\n'
            'func main() int32:\n'
            '    value: Empty = Empty()\n'
            '    return 0\n',
            'no tiene un __init__ utilizable',
        )

    def test_inheritance_flattens_fields_and_resolves_parent_methods(self):
        result = self.run_source(
            'class Base:\n'
            '    func __init__(value: int32) void:\n'
            '        self.base = value\n'
            '    func base_value() int32:\n'
            '        return self.base\n'
            'class Child(Base):\n'
            '    func __init__(value: int32) void:\n'
            '        super.__init__(value)\n'
            '        self.child = value + 1\n'
            '    func total() int32:\n'
            '        return self.base + self.child\n'
            'func main() int32:\n'
            '    child: Child = Child(4)\n'
            '    return child.base_value() + child.total()\n'
        )
        self.assertEqual(13, result.returncode)

    def test_inheritance_requires_parent_initializer_call(self):
        self.assert_compile_error(
            'class Base:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            'class Child(Base):\n'
            '    func __init__(value: int32) void:\n'
            '        self.other = value\n'
            'func main() int32:\n'
            '    return 0\n',
            'debe llamar a super.__init__',
        )

    def test_inheritance_rejects_field_collision(self):
        self.assert_compile_error(
            'class Base:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            'class Child(Base):\n'
            '    func __init__(value: int32) void:\n'
            '        super.__init__(value)\n'
            '        self.value = value\n'
            'func main() int32:\n'
            '    return 0\n',
            'ya existe en su clase padre',
        )

    def test_inheritance_rejects_unknown_parent_and_parent_cycles(self):
        self.assert_compile_error(
            'class Child(Unknown):\n'
            '    pass\n'
            'func main() int32:\n'
            '    return 0\n',
            'clase padre Unknown.*no existe',
        )
        self.assert_compile_error(
            'class First(Second):\n'
            '    pass\n'
            'class Second(First):\n'
            '    pass\n'
            'func main() int32:\n'
            '    return 0\n',
            'Ciclo de herencia detectado',
        )

    def test_inheritance_only_accepts_class_parent(self):
        self.assert_compile_error(
            'struct Plain:\n'
            '    value: int32\n'
            'class Child(Plain):\n'
            '    pass\n'
            'func main() int32:\n'
            '    return 0\n',
            'solo puede heredar de otra class',
        )

    def test_self_is_not_reassignable_and_cannot_be_declared(self):
        self.assert_compile_error(
            'class Box:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func bad() int32:\n'
            '        self = self\n'
            '        return 0\n'
            'func main() int32:\n'
            '    return 0\n',
            'receptor self.*no puede reasignarse',
        )
        self.assert_compile_error(
            'class Box:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func bad(self: int32) int32:\n'
            '        return self\n'
            'func main() int32:\n'
            '    return 0\n',
            'parametro self esta duplicado|parametro llamado self|'
            'no puede declarar.*self',
        )

    def test_access_hooks_are_not_inserted_inside_class_methods(self):
        result = self.run_source(
            'class Guarded:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __ongetter__(name: chain, length: Len_t) int32:\n'
            '        return 0\n'
            '    func __onsetter__(name: chain, length: Len_t) int32:\n'
            '        return 0\n'
            '    func read_internal() int32:\n'
            '        return self.value\n'
            'func main() int32:\n'
            '    guarded: Guarded = Guarded(7)\n'
            '    return guarded.read_internal()\n'
        )
        self.assertEqual(7, result.returncode)

    def test_access_hooks_run_before_external_get_and_set(self):
        module = self.compile_module(
            'class Guarded:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __ongetter__(name: chain, length: Len_t) int32:\n'
            '        return 1\n'
            '    func __onsetter__(name: chain, length: Len_t) int32:\n'
            '        return 1\n'
            'func main() int32:\n'
            '    guarded: Guarded = Guarded(7)\n'
            '    guarded.value = 8\n'
            '    return guarded.value\n'
        )
        main = module[module.index('define internal i32 @"__bagron_main"'):]
        setter_call = main.index('call i32 @"Guarded____onsetter__"')
        setter_store = main.index('store i32 8')
        getter_call = main.index('call i32 @"Guarded____ongetter__"')
        getter_load = main.index('load i32')
        self.assertLess(setter_call, setter_store)
        self.assertLess(getter_call, getter_load)

    def test_after_hooks_run_after_external_get_and_set(self):
        module = self.compile_module(
            'class Guarded:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    @after\n'
            '    func __ongetter__(name: chain, length: Len_t) int32:\n'
            '        return 1\n'
            '    @after\n'
            '    func __onsetter__(name: chain, length: Len_t) int32:\n'
            '        return 1\n'
            'func main() int32:\n'
            '    guarded: Guarded = Guarded(7)\n'
            '    guarded.value = 8\n'
            '    return guarded.value\n'
        )
        main = module[module.index('define internal i32 @"__bagron_main"'):]
        setter_store = main.index('store i32 8')
        setter_call = main.index('call i32 @"Guarded____onsetter__"')
        getter_load = main.index('load i32')
        getter_call = main.index('call i32 @"Guarded____ongetter__"')
        self.assertLess(setter_store, setter_call)
        self.assertLess(getter_load, getter_call)

    def test_access_hook_denial_traps_external_access(self):
        module = self.compile_module(
            'class Guarded:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __ongetter__(name: chain, length: Len_t) int32:\n'
            '        return 0\n'
            '    func __onsetter__(name: chain, length: Len_t) int32:\n'
            '        return 0\n'
            'func main() int32:\n'
            '    guarded: Guarded = Guarded(7)\n'
            '    guarded.value = 8\n'
            '    return guarded.value\n'
        )
        main = module[module.index('define internal i32 @"__bagron_main"'):]
        self.assertIn('call void @"llvm.trap"()', main)
        self.assertIn('call i32 @"Guarded____ongetter__"', main)
        self.assertIn('call i32 @"Guarded____onsetter__"', main)

    def test_eq_magic_method_controls_external_condition(self):
        result = self.run_source(
            'class Flag:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __eq__() bool:\n'
            '        return self.value == 7\n'
            'func main() int32:\n'
            '    flag: Flag = Flag(7)\n'
            '    if flag:\n'
            '        return 9\n'
            '    return 0\n'
        )
        self.assertEqual(9, result.returncode)

    def test_class_condition_without_eq_is_false(self):
        result = self.run_source(
            'class Flag:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            'func main() int32:\n'
            '    flag: Flag = Flag(7)\n'
            '    if flag:\n'
            '        return 1\n'
            '    return 0\n'
        )
        self.assertEqual(0, result.returncode)

    def test_all_supported_math_magic_methods_return_classes(self):
        result = self.run_source(
            'class Number:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __add__(other: Number) Number:\n'
            '        return Number(self.value + other.value)\n'
            '    func __sub__(other: Number) Number:\n'
            '        return Number(self.value - other.value)\n'
            '    func __mul__(other: Number) Number:\n'
            '        return Number(self.value * other.value)\n'
            '    func __truediv__(other: Number) Number:\n'
            '        return Number(self.value / other.value)\n'
            '    func __mod__(other: Number) Number:\n'
            '        return Number(self.value % other.value)\n'
            '    func __and__(other: Number) Number:\n'
            '        return Number(self.value & other.value)\n'
            '    func __or__(other: Number) Number:\n'
            '        return Number(self.value | other.value)\n'
            '    func __xor__(other: Number) Number:\n'
            '        return Number(self.value ^ other.value)\n'
            '    func __shl__(other: Number) Number:\n'
            '        return Number(self.value << other.value)\n'
            '    func __shr__(other: Number) Number:\n'
            '        return Number(self.value >> other.value)\n'
            '    func __pos__() Number:\n'
            '        return Number(self.value)\n'
            '    func __neg__() Number:\n'
            '        return Number(-self.value)\n'
            'func main() int32:\n'
            '    left: Number = Number(6)\n'
            '    right: Number = Number(2)\n'
            '    a: Number = left + right\n'
            '    b: Number = left - right\n'
            '    c: Number = left * right\n'
            '    d: Number = left / right\n'
            '    e: Number = left % right\n'
            '    f: Number = left & right\n'
            '    g: Number = left | right\n'
            '    h: Number = left ^ right\n'
            '    i: Number = left << right\n'
            '    j: Number = left >> right\n'
            '    k: Number = +left\n'
            '    l: Number = -left\n'
            '    return a.value + b.value + c.value + d.value + e.value + '
            '        f.value + g.value + h.value + i.value + j.value + '
            '        k.value + l.value\n'
        )
        self.assertEqual(64, result.returncode)

    def test_math_magic_methods_are_not_inserted_inside_class_methods(self):
        self.assert_compile_error(
            'class Number:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __add__(other: Number) Number:\n'
            '        return Number(self.value + other.value)\n'
            '    func invalid(other: Number) Number:\n'
            '        return self + other\n'
            'func main() int32:\n'
            '    return 0\n',
            'operandos de una operacion aritmetica|operador no soportado|'
            'operacion no soportada',
        )

    def test_del_calls_deletion_and_is_noop_without_it(self):
        result = self.run_source(
            'class Resource:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __deletion__() void:\n'
            '        self.value = 99\n'
            '        return\n'
            '    func read() int32:\n'
            '        return self.value\n'
            'class Plain:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            'func main() int32:\n'
            '    resource: Resource = Resource(7)\n'
            '    Del resource\n'
            '    plain: Plain = Plain(4)\n'
            '    Del plain\n'
            '    return resource.read() + plain.value\n'
        )
        self.assertEqual(103, result.returncode)

    def test_del_resolves_inherited_deletion_method(self):
        result = self.run_source(
            'class Base:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __deletion__() void:\n'
            '        self.value = 50\n'
            '        return\n'
            'class Child(Base):\n'
            '    func __init__(value: int32) void:\n'
            '        super.__init__(value)\n'
            '    func read() int32:\n'
            '        return self.value\n'
            'func main() int32:\n'
            '    child: Child = Child(1)\n'
            '    Del child\n'
            '    return child.read()\n'
        )
        self.assertEqual(50, result.returncode)

    def test_del_emits_only_existing_deletion_hooks(self):
        module = self.compile_module(
            'class Resource:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __deletion__() void:\n'
            '        return\n'
            'class Plain:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            'func main() int32:\n'
            '    resource: Resource = Resource(1)\n'
            '    Del resource\n'
            '    plain: Plain = Plain(2)\n'
            '    Del plain\n'
            '    return 0\n'
        )
        self.assertIn('call void @"Resource____deletion__"', module)
        self.assertNotIn('Plain____deletion__', module)

    def test_del_accepts_parentheses_and_repeats_the_hook(self):
        result = self.run_source(
            'class Resource:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __deletion__() void:\n'
            '        self.value += 1\n'
            '        return\n'
            'func main() int32:\n'
            '    resource: Resource = Resource(3)\n'
            '    Del (resource)\n'
            '    Del resource\n'
            '    return resource.value\n'
        )
        self.assertEqual(5, result.returncode)

    def test_del_nested_class_member(self):
        result = self.run_source(
            'class Inner:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __deletion__() void:\n'
            '        self.value = 40\n'
            '        return\n'
            'class Outer:\n'
            '    func __init__(value: int32) void:\n'
            '        self.inner = Inner(value)\n'
            '    func read() int32:\n'
            '        return self.inner.value\n'
            'func main() int32:\n'
            '    outer: Outer = Outer(7)\n'
            '    Del outer.inner\n'
            '    return outer.read()\n'
        )
        self.assertEqual(40, result.returncode)

    def test_del_temporary_constructor_runs_deletion(self):
        module = self.compile_module(
            'class Resource:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __deletion__() void:\n'
            '        self.value = 9\n'
            '        return\n'
            'func main() int32:\n'
            '    Del Resource(1)\n'
            '    return 0\n'
        )
        main = module[module.index('define internal i32 @"__bagron_main"'):]
        self.assertIn('call void @"Resource____deletion__"', main)

    def test_del_temporary_method_result_runs_deletion(self):
        module = self.compile_module(
            'class Resource:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __deletion__() void:\n'
            '        self.value = 9\n'
            '        return\n'
            'class Factory:\n'
            '    @static\n'
            '    func make(value: int32) Resource:\n'
            '        return Resource(value)\n'
            'func main() int32:\n'
            '    Del Factory.make(1)\n'
            '    return 0\n'
        )
        main = module[module.index('define internal i32 @"__bagron_main"'):]
        self.assertIn('call void @"Resource____deletion__"', main)

    def test_del_inside_method_uses_the_instance_context(self):
        result = self.run_source(
            'class Resource:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __deletion__() void:\n'
            '        self.value = 12\n'
            '        return\n'
            '    func dispose() void:\n'
            '        Del self\n'
            '        return\n'
            '    func read() int32:\n'
            '        return self.value\n'
            'func main() int32:\n'
            '    resource: Resource = Resource(12)\n'
            '    resource.dispose()\n'
            '    return resource.read()\n'
        )
        self.assertEqual(12, result.returncode)

    def test_del_prefers_child_deletion_over_inherited_one(self):
        result = self.run_source(
            'class Base:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func __deletion__() void:\n'
            '        self.value = 1\n'
            '        return\n'
            'class Child(Base):\n'
            '    func __init__(value: int32) void:\n'
            '        super.__init__(value)\n'
            '    func __deletion__() void:\n'
            '        self.value = 2\n'
            '        return\n'
            '    func read() int32:\n'
            '        return self.value\n'
            'func main() int32:\n'
            '    child: Child = Child(1)\n'
            '    Del child\n'
            '    return child.read()\n'
        )
        self.assertEqual(2, result.returncode)

    def test_del_rejects_non_class_values(self):
        self.assert_compile_error(
            'func main() int32:\n'
            '    value: int32 = 1\n'
            '    Del value\n'
            '    return 0\n',
            'Del en main requiere una instancia escalar de class',
        )

    def test_del_rejects_class_pointers_and_arrays(self):
        self.assert_compile_error(
            'class Resource:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            'func main() int32:\n'
            '    resource: Resource = Resource(1)\n'
            '    pointer *: Resource = $resource\n'
            '    Del pointer\n'
            '    return 0\n',
            'Del en main requiere una instancia escalar de class',
        )
        self.assert_compile_error(
            'class Resource:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            'func main() int32:\n'
            '    resources: Resource[2]\n'
            '    Del resources\n'
            '    return 0\n',
            'Del en main requiere una instancia escalar de class',
        )
        self.assert_compile_error(
            'struct Pair:\n'
            '    value: int32\n'
            'func main() int32:\n'
            '    pair: Pair\n'
            '    Del pair\n'
            '    return 0\n',
            'Del en main requiere una instancia escalar de class',
        )

    def test_deletion_magic_signature_is_strict(self):
        cases = (
            (
                'class Broken:\n'
                '    func __deletion__(value: int32) void:\n'
                '        return\n',
                'no puede recibir parametros',
            ),
            (
                'class Broken:\n'
                '    func __deletion__() int32:\n'
                '        return 1\n',
                'debe retornar void',
            ),
            (
                'class Broken:\n'
                '    @static\n'
                '    func __deletion__() void:\n'
                '        return\n',
                'no puede ser @static',
            ),
            (
                'class Broken:\n'
                '    @after\n'
                '    func __deletion__() void:\n'
                '        return\n',
                'solo puede usarse en los hooks de acceso',
            ),
        )
        for declaration, pattern in cases:
            with self.subTest(pattern=pattern):
                self.assert_compile_error(
                    declaration + 'func main() int32:\n    return 0\n',
                    pattern,
                )

    def test_magic_method_signatures_reject_static_and_invalid_returns(self):
        self.assert_compile_error(
            'class Broken:\n'
            '    @static\n'
            '    func __eq__() bool:\n'
            '        return true\n'
            'func main() int32:\n'
            '    return 0\n',
            'metodo magico.*no puede ser @static',
        )
        self.assert_compile_error(
            'class Broken:\n'
            '    func __ongetter__(name: int32, length: Len_t) int32:\n'
            '        return 1\n'
            'func main() int32:\n'
            '    return 0\n',
            'Len_t solo puede asociarse|debe recibir un chain y su Len_t',
        )
        self.assert_compile_error(
            'class Broken:\n'
            '    func __eq__(value: int32) int32:\n'
            '        return value\n'
            'func main() int32:\n'
            '    return 0\n',
            'no puede recibir parametros|debe retornar bool',
        )
        self.assert_compile_error(
            'class Broken:\n'
            '    func __add__() void:\n'
            '        return\n'
            'func main() int32:\n'
            '    return 0\n',
            'debe recibir exactamente un parametro explicito',
        )

    def test_never_function_can_terminate_main_without_return(self):
        module = self.compile_module(
            'func stop() Never:\n'
            '    pass\n'
            'func main() int32:\n'
            '    stop()\n'
        )
        stop = module[module.index('define void @"stop"'):]
        main = module[module.index('define internal i32 @"__bagron_main"'):]
        self.assertIn('unreachable', stop)
        self.assertIn('call void @"stop"()', main)
        self.assertIn('unreachable', main)

    def test_never_call_satisfies_branch_return_analysis(self):
        self.compile_source(
            'func stop() Never:\n'
            '    pass\n'
            'func choose(flag: bool) int32:\n'
            '    if flag:\n'
            '        stop()\n'
            '    else:\n'
            '        return 1\n'
            'func main() int32:\n'
            '    return choose(false)\n'
        )

    def test_void_function_can_end_in_never_call(self):
        self.compile_source(
            'func stop() Never:\n'
            '    pass\n'
            'func wrapper() void:\n'
            '    stop()\n'
            'func main() int32:\n'
            '    return 0\n'
        )

    def test_never_cannot_be_used_as_value_or_condition(self):
        self.assert_compile_error(
            'func stop() Never:\n'
            '    pass\n'
            'func main() int32:\n'
            '    result: int32 = stop()\n'
            '    return result\n',
            'funcion Never solo puede llamarse como sentencia|valor inicial',
        )
        self.assert_compile_error(
            'func stop() Never:\n'
            '    pass\n'
            'func main() int32:\n'
            '    if stop():\n'
            '        return 1\n'
            '    return 0\n',
            'funcion Never solo puede llamarse como sentencia',
        )

    def test_never_cannot_be_storage_or_parameter(self):
        self.assert_compile_error(
            'func main() int32:\n'
            '    value: Never = 0\n'
            '    return 0\n',
            'no puede usar Never como almacenamiento',
        )
        self.assert_compile_error(
            'func invalid(value: Never) int32:\n'
            '    return 0\n'
            'func main() int32:\n'
            '    return 0\n',
            'parametro value no puede usar Never',
        )

    def test_never_function_cannot_return(self):
        self.assert_compile_error(
            'func invalid() Never:\n'
            '    return\n'
            'func main() int32:\n'
            '    return 0\n',
            'funcion Never invalid no puede usar return',
        )

    def test_never_is_not_a_pointer_or_array_type(self):
        self.assert_compile_error(
            'func invalid() Never *:\n'
            '    pass\n'
            'func main() int32:\n'
            '    return 0\n',
            'Never solo puede usarse como retorno escalar',
        )
        self.assert_compile_error(
            'func main() int32:\n'
            '    values: Never[2] = {1, 2}\n'
            '    return 0\n',
            'no puede usar Never como almacenamiento',
        )


if __name__ == '__main__':
    unittest.main()

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class ClassBoundaryTests(unittest.TestCase):
    """Stress class invariants that are easy to break at semantic boundaries."""

    def compile_source(self, source: str, *, executable: bool = False):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        return Compiler().compile(path, executable=executable)

    def run_source(self, source: str) -> subprocess.CompletedProcess[str]:
        artifacts = self.compile_source(source, executable=True)
        return subprocess.run(
            [str(artifacts.executable)],
            capture_output=True,
            timeout=10,
            check=False,
            text=True,
        )

    def compile_semantics(self, source: str) -> Compiler:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        compiler = Compiler()
        compiler.compile(path, executable=False)
        return compiler

    def assert_compile_error(self, source: str, pattern: str) -> None:
        with self.assertRaisesRegex(CompilationError, pattern):
            self.compile_source(source)

    def test_initializer_rejects_aliases_compound_writes_and_duplicate_fields(self):
        self.assert_compile_error(
            'class Broken:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '        self.value += 1\n'
            'func main() int32:\n'
            '    return 0\n',
            'debe usar =',
        )
        self.assert_compile_error(
            'class Broken:\n'
            '    func __init__(value: int32) void:\n'
            '        other: Broken = value\n'
            '        self.value = value\n'
            'func main() int32:\n'
            '    return 0\n',
            'solo admite super.*asignaciones directas a self',
        )
        self.assert_compile_error(
            'class Broken:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '        self.value = value\n'
            'func main() int32:\n'
            '    return 0\n',
            'ya fue inicializado',
        )

    def test_frontend_initializer_has_exactly_one_visible_input_and_void_result(self):
        self.assert_compile_error(
            'class Broken:\n'
            '    func __frontend__(left: chain, right: chain) void:\n'
            '        self.value = 1\n'
            'func main() int32:\n'
            '    return 0\n',
            '__frontend__ debe recibir exactamente un',
        )
        self.assert_compile_error(
            'class Broken:\n'
            '    func __frontend__(value: chain) int32:\n'
            '        self.value = 1\n'
            'func main() int32:\n'
            '    return 0\n',
            '__frontend__ debe retornar void',
        )

    def test_inheritance_rejects_bad_super_arguments(self):
        self.assert_compile_error(
            'class Base:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            'class Child(Base):\n'
            '    func __init__() void:\n'
            '        super.__init__()\n'
            'func main() int32:\n'
            '    return 0\n',
            'esperaba 1 argumentos y recibio 0',
        )

    def test_private_methods_remain_private_through_inheritance(self):
        self.assert_compile_error(
            'class Base:\n'
            '    func __init__() void:\n'
            '        pass\n'
            '    func _secret() int32:\n'
            '        return 7\n'
            'class Child(Base):\n'
            '    func __init__() void:\n'
            '        super.__init__()\n'
            '    func read() int32:\n'
            '        return self._secret()\n'
            'func main() int32:\n'
            '    child: Child = Child()\n'
            '    return child.read()\n',
            'metodo privado',
        )

    def test_frozen_rejects_indirect_self_mutation_but_allows_nested_value_mutation(self):
        self.assert_compile_error(
            '@frozen\n'
            'class Box:\n'
            '    func __init__(value: int32) void:\n'
            '        self.value = value\n'
            '    func mutate() void:\n'
            '        pointer *: int32 = $self.value\n'
            '        (pointer) = 3\n'
            '        return\n'
            'func main() int32:\n'
            '    return 0\n',
            'clase @frozen Box.*no permite modificar',
        )
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
            '    outer.inner.value = 9\n'
            '    return outer.inner.value\n'
        )
        self.assertEqual(9, result.returncode)

    def test_class_layout_preserves_typed_zero_fields_and_alignment(self):
        compiler = self.compile_semantics(
            '@align(16)\n'
            'class Aligned:\n'
            '    func __init__() void:\n'
            '        self.bytes: uint8[4]\n'
            '    func first() uint8:\n'
            '        return self.bytes[0]\n'
            'func main() int32:\n'
            '    value: Aligned = Aligned()\n'
            '    return 0\n'
        )
        symbol = compiler.storage.types['Aligned']
        self.assertEqual(16, symbol.alignment)
        self.assertEqual('uint8', symbol.fields[0].type_spec.name)

    def test_invalid_class_decorators_and_magic_hooks_are_diagnosed(self):
        self.assert_compile_error(
            '@packed\n'
            '@packed\n'
            'class Broken:\n'
            '    pass\n'
            'func main() int32:\n'
            '    return 0\n',
            'decorador @packed esta repetido',
        )
        self.assert_compile_error(
            'class Broken:\n'
            '    func __ongetter__(name: chain, length: Len_t) bool:\n'
            '        return true\n'
            'func main() int32:\n'
            '    return 0\n',
            'debe retornar int32',
        )


if __name__ == '__main__':
    unittest.main()

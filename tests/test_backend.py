from __future__ import annotations

import tempfile
import unittest
import subprocess
from pathlib import Path

from core.compiler import CompilationError, Compiler


class GlobalBackendTests(unittest.TestCase):
    def compile_source(self, source: str, add_main: bool = True) -> str:
        if add_main:
            source = source.rstrip() + '\n\nfunc main() int:\n    return 0\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(source, encoding='utf-8')
            output = Compiler().compile(path, executable=False)
            return Path(output).read_text(encoding='utf-8')

    def test_emits_literals_bint_arrays_and_const_references(self):
        module = self.compile_source(
            'base: const int = 10\n'
            'copy: int = base\n'
            'small: Bint<5> = 15\n'
            'mask: uBint<5> = 31\n'
            'values: uBint<5>[] = {1, 2, 3}\n'
        )

        self.assertIn('global i32 10', module)
        self.assertIn('global i5 15', module)
        self.assertIn('global [3 x i5]', module)

    def test_emits_decimal_literals(self):
        module = self.compile_source('value: double = 3.141516\n')

        self.assertIn('global double ', module)

    def test_emits_char_byte_arrays_and_static_chain(self):
        module = self.compile_source(
            'nombre: char[10] = "Hola"\n'
            'bytes: byte[6] = "x0x0xb"\n'
            'mensaje: chain = "Hola"\n'
            'letra: char = "A"\n'
            'octeto: byte = 255\n'
        )

        self.assertIn('@"nombre" = global [10 x i8]', module)
        self.assertIn('@"bytes" = global [6 x i8]', module)
        self.assertIn('@"mensaje" = constant [5 x i8]', module)
        self.assertIn('global i8 65', module)
        self.assertIn('global i8 255', module)

    def test_builds_and_runs_local_char_and_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int:\n'
                '    letra: char = "A"\n'
                '    octeto: byte = 7\n'
                '    return 7\n',
                encoding='utf-8',
            )
            artifacts = Compiler().compile(path)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(7, result.returncode)

    def test_emits_struct_mold_enum_and_flags_types(self):
        module = self.compile_source(
            'enum Estado:\n'
            '    LISTO,\n'
            'struct Punto:\n'
            '    x: int\n'
            '    estado: Estado\n'
            'mold Base:\n'
            '    punto: Punto\n'
            'flags Permisos:\n'
            '    leer: uBint<1> = 1\n'
            '    escribir: uBint<1> = 0\n'
            'punto: Punto\n'
            'base: Base\n'
            'permisos: Permisos\n'
        )

        self.assertIn('"Punto" = type {i32, i32}', module)
        self.assertIn('"Base" = type {%"Punto"}', module)
        self.assertIn('"Permisos" = type <{i1, i1}>', module)
        self.assertIn('@"punto" = global %"Punto" zeroinitializer', module)
        self.assertIn('@"base" = global %"Base" zeroinitializer', module)
        self.assertIn('@"permisos" = global %"Permisos" zeroinitializer', module)

    def test_emits_enum_underlying_width(self):
        module = self.compile_source(
            'enum Estado int8:\n'
            '    LISTO,\n'
            'estado: Estado\n'
        )

        self.assertIn('@"estado" = global i8 0', module)

    def test_emits_int_main_as_llvm_entrypoint(self):
        module = self.compile_source('value: int = 1\n')

        self.assertIn('define internal i32 @"__bagron_main"()', module)
        self.assertIn('define i32 @"main"()', module)
        self.assertIn('ret i32 0', module)

    def test_builds_and_runs_main_exit_codes(self):
        for code, expected in (('0', 0), ('7', 7)):
            with self.subTest(code=code):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / '_main.bg'
                    path.write_text(
                        'func main() int:\n'
                        f'    return {code}\n',
                        encoding='utf-8',
                    )
                    artifacts = Compiler().compile(path)
                    self.assertTrue(artifacts.ir.exists())
                    self.assertTrue(artifacts.object_file.exists())
                    self.assertTrue(artifacts.executable.exists())
                    result = subprocess.run(
                        [str(artifacts.executable)],
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                    self.assertEqual(expected, result.returncode)

    def test_emits_function_return_sum_and_call(self):
        module = self.compile_source(
            'func sumar(a: int, b: int) int:\n'
            '    return a + b\n'
            'func main() int:\n'
            '    return sumar(2, 3)\n',
            add_main=False,
        )

        self.assertIn('define i32 @"sumar"(i32 %"a", i32 %"b")', module)
        self.assertIn('load i32, i32* %"a.addr"', module)
        self.assertIn('load i32, i32* %"b.addr"', module)
        self.assertIn('add i32', module)
        self.assertIn('call i32 @"sumar"(i32 2, i32 3)', module)

    def test_runs_function_return_sum_and_call(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func sumar(a: int, b: int) int:\n'
                '    return a + b\n'
                'func main() int:\n'
                '    return sumar(2, 3)\n',
                encoding='utf-8',
            )
            artifacts = Compiler().compile(path)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(5, result.returncode)

    def test_builds_and_runs_void_function_call(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func touch(value: int) void:\n'
                '    copy: int = value\n'
                '    return\n'
                'func main() int:\n'
                '    touch(4)\n'
                '    return 0\n',
                encoding='utf-8',
            )
            artifacts = Compiler().compile(path)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

            module = artifacts.ir.read_text(encoding='utf-8')

        self.assertEqual(0, result.returncode)
        self.assertIn('define void @"touch"(i32', module)
        self.assertIn('call void @"touch"(i32', module)

    def test_builds_and_runs_local_declarations_and_assignments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int:\n'
                '    result: int = 2\n'
                '    result += 3\n'
                '    result = result * 2\n'
                '    return result\n',
                encoding='utf-8',
            )
            artifacts = Compiler().compile(path)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(10, result.returncode)

    def test_builds_and_runs_local_parameter_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func calcular(value: int) int:\n'
                '    result: int = value\n'
                '    result += 2\n'
                '    return result\n'
                'func main() int:\n'
                '    return calcular(3)\n',
                encoding='utf-8',
            )
            artifacts = Compiler().compile(path)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(5, result.returncode)

    def test_builds_and_runs_assignment_without_initializer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int:\n'
                '    result: int\n'
                '    result = 7\n'
                '    return result\n',
                encoding='utf-8',
            )
            artifacts = Compiler().compile(path)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(7, result.returncode)

    def test_builds_and_runs_numeric_for(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int:\n'
                '    for i: int32 ran (1, 4, 1):\n'
                '        pass\n'
                '    for j: int8 ran (3, 0, -1):\n'
                '        pass\n'
                '    return 0\n',
                encoding='utf-8',
            )
            artifacts = Compiler().compile(path)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)

    def test_builds_and_runs_if_elif_else_while_and_nested_for(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int:\n'
                '    total: int = 0\n'
                '    i: int = 0\n'
                '    while i < 3:\n'
                '        if i == 0:\n'
                '            total += 1\n'
                '        elif i == 1:\n'
                '            total += 2\n'
                '        else:\n'
                '            total += 3\n'
                '        i += 1\n'
                '    for outer: int32 ran (0, 2, 1):\n'
                '        for inner: int8 ran (0, 2, 1):\n'
                '            total += 1\n'
                '    return total\n',
                encoding='utf-8',
            )
            artifacts = Compiler().compile(path)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(10, result.returncode)

    def test_builds_and_runs_for_with_nested_while_and_if(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int:\n'
                '    total: int = 0\n'
                '    for i: int32 ran (0, 3, 1):\n'
                '        j: int = 0\n'
                '        while j < 2:\n'
                '            if i == 1:\n'
                '                total += 2\n'
                '            else:\n'
                '                total += 1\n'
                '            j += 1\n'
                '    return total\n',
                encoding='utf-8',
            )
            artifacts = Compiler().compile(path)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(8, result.returncode)

    def test_builds_and_runs_break_and_continue_in_nested_control_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int:\n'
                '    total: int = 0\n'
                '    for i: int ran (0, 5, 1):\n'
                '        if i == 1:\n'
                '            continue\n'
                '        if i == 4:\n'
                '            break\n'
                '        total += 1\n'
                '    return total\n',
                encoding='utf-8',
            )
            artifacts = Compiler().compile(path)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(3, result.returncode)

    def test_rejects_mutable_global_reference(self):
        with self.assertRaisesRegex(CompilationError, 'global mutable base'):
            self.compile_source('base: int = 10\ncopy: int = base\n')

    def test_rejects_mutable_reference_inside_array(self):
        with self.assertRaisesRegex(CompilationError, 'global mutable base'):
            self.compile_source(
                'base: int = 10\n'
                'values: int[] = {base}\n'
            )

    def test_rejects_invalid_arch(self):
        with self.assertRaisesRegex(CompilationError, 'valor invalido'):
            self.compile_source("clause Arch 'invalid'\nvalue: int = 1\n")

    def test_accepts_explicit_llvm_triple(self):
        from llvmlite import binding as llvm

        triple = llvm.get_default_triple()
        module = self.compile_source(
            f"clause Arch '{triple}'\n"
            'value: int = 1\n'
        )
        self.assertIn(f'target triple = "{triple}"', module)

    def test_requires_global_main(self):
        with self.assertRaisesRegex(CompilationError, 'funcion global main'):
            self.compile_source('value: int = 1\n', add_main=False)

    def test_main_requires_int_without_parameters(self):
        with self.assertRaisesRegex(CompilationError, 'debe retornar int'):
            self.compile_source(
                'func main() bool:\n'
                '    return true\n',
                add_main=False,
            )

        with self.assertRaisesRegex(CompilationError, 'no puede recibir parametros'):
            self.compile_source(
                'func main(value: int) int:\n'
                '    return 0\n',
                add_main=False,
            )


if __name__ == '__main__':
    unittest.main()

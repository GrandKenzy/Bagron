from __future__ import annotations

import tempfile
import unittest
import subprocess
from pathlib import Path

from core.compiler import CompilationError, Compiler


class GlobalBackendTests(unittest.TestCase):
    def compile_source(
        self,
        source: str,
        add_main: bool = True,
        optimization_profile: str | None = 'dev',
    ) -> str:
        if (
            optimization_profile is not None
            and 'clause Optimizations' not in source
        ):
            source = f"clause Optimizations '{optimization_profile}'\n" + source
        if add_main:
            source = source.rstrip() + '\n\nfunc main() int32:\n    return 0\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(source, encoding='utf-8')
            output = Compiler().compile(path, executable=False)
            return Path(output).read_text(encoding='utf-8')

    def test_emits_literals_and_const_references(self):
        module = self.compile_source(
            'base: const int32 = 10\n'
            'copy: int32 = base\n'
        )

        self.assertIn('global i32 10', module)

    def test_emits_decimal_literals(self):
        module = self.compile_source('value: double = 3.141516\n')

        self.assertIn('global double ', module)

    def test_emits_middle_float_and_double_function_arithmetic(self):
        module = self.compile_source(
            'func add_middle(left: middle, right: middle) middle:\n'
            '    return left + right\n'
            'func add_float(left: float, right: float) float:\n'
            '    return left * right + 1.0\n'
            'func add_double(left: double, right: double) double:\n'
            '    return left / right\n'
            'func less_than(left: float, right: float) bool:\n'
            '    return left < right\n'
            'func main() int32:\n'
            '    half: middle = add_middle(1.5, 2.5)\n'
            '    single: float = add_float(2.0, 3.0)\n'
            '    wide: double = add_double(9.0, 3.0)\n'
            '    return 0\n',
            add_main=False,
        )

        self.assertIn('define half @"add_middle"', module)
        self.assertIn('fadd half', module)
        self.assertIn('define float @"add_float"', module)
        self.assertIn('fmul float', module)
        self.assertIn('define double @"add_double"', module)
        self.assertIn('fdiv double', module)
        self.assertIn('define i1 @"less_than"', module)
        self.assertIn('fcmp', module)

    def test_emits_inline_hint_for_inline_function(self):
        module = self.compile_source(
            'inline func helper(value: int32) int32:\n'
            '    return value\n'
        )

        self.assertIn('define i32 @"helper"', module)
        self.assertIn('inlinehint', module)

    def test_prod_expands_bagron_inline_calls_before_codegen(self):
        module = self.compile_source(
            'inline func helper(value: int32) int32:\n'
            '    return value + 1\n'
            'func caller(value: int32) int32:\n'
            '    return helper(value)\n'
            'func main() int32:\n'
            '    return caller(1)\n',
            add_main=False,
            optimization_profile='prod',
        )

        self.assertIn('alwaysinline', module)
        self.assertNotIn('call i32 @"helper"', module)
        self.assertIn('add i32', module)

    def test_optimization_profiles_publish_the_selected_ir(self):
        source = (
            'func sum_to(limit: uint32) uint32:\n'
            '    total: uint32 = 0\n'
            '    for i: uint32 ran (0, limit, 1):\n'
            '        total += i\n'
            '    return total\n'
        )

        development = self.compile_source(source, optimization_profile='dev')
        production = self.compile_source(source, optimization_profile='prod')
        high = self.compile_source(source, optimization_profile='high')
        default = self.compile_source(source, optimization_profile=None)

        self.assertIn('i.addr', development)
        self.assertNotIn('i.addr', production)
        self.assertNotIn('i.addr', high)
        self.assertNotIn('i.addr', default)
        self.assertIn('phi i32', production)

    def test_optimized_for_keeps_addressable_iterator_storage(self):
        module = self.compile_source(
            'extern "kernel32":\n'
            '    KeepIterator(value *: uint32) void\n'
            '@unsafe\n'
            'func walk(limit: uint32) uint32:\n'
            '    total: uint32 = 0\n'
            '    for i: uint32 ran (0, limit, 1):\n'
            '        KeepIterator($i)\n'
            '        total += i\n'
            '    return total\n',
            optimization_profile='prod',
        )

        self.assertIn('i.addr', module)
        self.assertIn('KeepIterator', module)

    def test_optimized_volatile_accesses_survive_ir_pipeline(self):
        module = self.compile_source(
            'volatile struct MMIO:\n'
            '    value: uint32\n'
            '@unsafe\n'
            'func touch(registers *: MMIO) uint32:\n'
            '    (registers).value = 7\n'
            '    return (registers).value\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    registers: MMIO\n'
            '    observed: uint32 = touch($registers)\n'
            '    return 0\n',
            add_main=False,
            optimization_profile='prod',
        )

        self.assertIn('store volatile i32', module)
        self.assertIn('load volatile i32', module)

    def test_emits_char_byte_arrays_and_static_chain(self):
        module = self.compile_source(
            'nombre: char[10] = "Hola"\n'
            'inferido: char[] = "Hola"\n'
            'bytes: byte[6] = "x0x0xb"\n'
            'mensaje: chain = "Hola"\n'
            'letra: char = "A"\n'
            'octeto: byte = 255\n'
        )

        self.assertIn('@"nombre" = global [10 x i8]', module)
        self.assertIn('@"inferido" = global [5 x i8]', module)
        self.assertIn(
            '@"inferido" = global [5 x i8] '
            '[i8 72, i8 111, i8 108, i8 97, i8 0]',
            module,
        )
        self.assertIn('@"bytes" = global [6 x i8]', module)
        self.assertIn('@"mensaje" = constant [5 x i8]', module)
        self.assertIn('global i8 65', module)
        self.assertIn('global i8 255', module)

    def test_builds_and_runs_local_char_and_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int32:\n'
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
            '    x: int32\n'
            '    estado: Estado\n'
            'mold Base:\n'
            '    punto: Punto\n'
            'flags Permisos uint8:\n'
            '    leer: uBint<1> = 1\n'
            '    escribir: uBint<1> = 0\n'
            '    activo: bool = true\n'
            '    reservado: uBint<5> = 0\n'
            'punto: Punto\n'
            'base: Base\n'
            'permisos: Permisos\n'
        )

        self.assertIn('"Punto" = type {{i32, i32}}', module)
        self.assertIn('"Base" = type {[0 x <4 x i8>], {[8 x i8]}}', module)
        self.assertIn('"Permisos" = type {{i8}}', module)
        self.assertIn('@"punto" = global %"Punto" {{i32, i32}', module)
        self.assertIn('@"base" = global %"Base" zeroinitializer', module)
        self.assertIn('@"permisos" = global %"Permisos" {{i8} {i8 5}}', module)

    def test_builds_and_runs_struct_mold_and_flags_member_access(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'struct Punto:\n'
                '    x: int32\n'
                '    y: int32\n'
                'mold Vista:\n'
                '    entero: int32\n'
                '    crudo: uint32\n'
                'flags Estado uint8:\n'
                '    listo: uBint<1> = 1\n'
                '    modo: uBint<2> = 2\n'
                '    reservado: uBint<5> = 0\n'
                'func calcular() int32:\n'
                '    punto: Punto\n'
                '    punto.x = 4\n'
                '    punto.y = 3\n'
                '    vista: Vista\n'
                '    vista.entero = punto.x + punto.y\n'
                '    estado: Estado\n'
                '    estado.listo = 0\n'
                '    estado.modo += 1\n'
                '    if estado.listo == 0:\n'
                '        if estado.modo == 3:\n'
                '            if vista.crudo == 7:\n'
                '                return punto.x + punto.y\n'
                '    return 0\n'
                'func main() int32:\n'
                '    return calcular()\n',
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

    def test_emits_packed_aligned_volatile_and_msb_flags(self):
        module = self.compile_source(
            '@packed\n'
            '@align(8)\n'
            'struct Paquete:\n'
            '    etiqueta: byte\n'
            '    valor: int32\n'
            '@order_msb\n'
            'volatile flags Estado uint8:\n'
            '    activo: uBint<1> = 1\n'
            '    modo: uBint<2> = 2\n'
            '    reservado: uBint<5> = 0\n'
            'func inspeccionar() int32:\n'
            '    paquete: Paquete\n'
            '    paquete.etiqueta = 1\n'
            '    paquete.valor = 7\n'
            '    estado: Estado\n'
            '    estado.activo = 0\n'
            '    if estado.activo == 0:\n'
            '        return paquete.valor\n'
            '    return 0\n'
            'func main() int32:\n'
            '    return inspeccionar()\n',
            add_main=False,
        )

        self.assertIn('"Paquete" = type {[0 x <8 x i8>], <{i8, i32}>}', module)
        self.assertIn('alloca %"Paquete", align 8', module)
        self.assertIn('store i32 7, i32*', module)
        self.assertIn('align 1', module)
        self.assertIn('load volatile i8', module)
        self.assertIn('store volatile i8', module)
        self.assertIn('lshr i8', module)

    def test_emits_volatile_accesses_for_mmio_aggregates_and_pointers(self):
        module = self.compile_source(
            'struct Normal:\n'
            '    value: uint32\n'
            'volatile struct MMIO:\n'
            '    value: uint32\n'
            'volatile mold VistaMMIO:\n'
            '    value: uint32\n'
            'volatile flags EstadoMMIO uint8:\n'
            '    listo: bool = false\n'
            '    reservado: uBint<7> = 0\n'
            '@unsafe\n'
            'func leer_mmio(registros *: MMIO) uint32:\n'
            '    return (registros).value\n'
            '@unsafe\n'
            'func escribir_mmio(registros *: MMIO) void:\n'
            '    (registros).value = 7\n'
            '    return\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    normal: Normal\n'
            '    mmio: MMIO\n'
            '    vista: VistaMMIO\n'
            '    estado: EstadoMMIO\n'
            '    normal.value = 1\n'
            '    mmio.value = 2\n'
            '    vista.value = 3\n'
            '    estado.listo = true\n'
            '    escribir_mmio($mmio)\n'
            '    observado: uint32 = normal.value\n'
            '    lectura: uint32 = leer_mmio($mmio)\n'
            '    return 0\n',
            add_main=False,
        )

        self.assertIn('load volatile i32', module)
        self.assertIn('store volatile i32', module)
        self.assertIn('load volatile i8', module)
        self.assertIn('store volatile i8', module)
        self.assertIn('load i32', module)
        self.assertIn('store i32', module)

    def test_emits_enum_underlying_width(self):
        module = self.compile_source(
            'enum Estado int8:\n'
            '    LISTO,\n'
            'estado: Estado\n'
        )

        self.assertIn('@"estado" = global i8 0', module)

    def test_emits_int_main_as_llvm_entrypoint(self):
        module = self.compile_source('value: int32 = 1\n')

        self.assertIn('define internal i32 @"__bagron_main"()', module)
        self.assertIn('define i32 @"main"()', module)
        self.assertIn('ret i32 0', module)

    def test_builds_and_runs_main_exit_codes(self):
        for code, expected in (('0', 0), ('7', 7)):
            with self.subTest(code=code):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / '_main.bg'
                    path.write_text(
                        'func main() int32:\n'
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
            'func sumar(a: int32, b: int32) int32:\n'
            '    return a + b\n'
            'func main() int32:\n'
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
                'func sumar(a: int32, b: int32) int32:\n'
                '    return a + b\n'
                'func main() int32:\n'
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
                "clause Optimizations 'dev'\n"
                'func touch(value: int32) void:\n'
                '    copy: int32 = value\n'
                '    return\n'
                'func main() int32:\n'
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
                'func main() int32:\n'
                '    result: int32 = 2\n'
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
                'func calcular(value: int32) int32:\n'
                '    result: int32 = value\n'
                '    result += 2\n'
                '    return result\n'
                'func main() int32:\n'
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

    def test_rejects_scalar_assignment_without_initializer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int32:\n'
                '    result: int32\n'
                '    result = 7\n'
                '    return result\n',
                encoding='utf-8',
            )
            with self.assertRaisesRegex(
                CompilationError,
                'debe tener un inicializador',
            ):
                Compiler().compile(path)

    def test_builds_and_runs_numeric_for(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int32:\n'
                '    for i: uint32 ran (1, 4, 1):\n'
                '        pass\n'
                '    for j: uint32 ran (3, 6, 1):\n'
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

    def test_numeric_for_traps_on_runtime_zero_step(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int32:\n'
                '    step: uint32 = 0\n'
                '    for i: uint32 ran (0, 3, step):\n'
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

        self.assertNotEqual(0, result.returncode)

    def test_numeric_for_uses_unsigned_comparisons_above_signed_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int32:\n'
                '    count: int32 = 0\n'
                '    for i: uint32 ran (2147483648, 2147483651, 1):\n'
                '        count += 1\n'
                '    return count\n',
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

    def test_numeric_for_does_not_wrap_when_next_value_reaches_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int32:\n'
                '    count: int32 = 0\n'
                '    for i: uint32 ran (4294967294, 4294967295, 2):\n'
                '        count += 1\n'
                '    return count\n',
                encoding='utf-8',
            )
            artifacts = Compiler().compile(path)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(1, result.returncode)

    def test_builds_and_runs_if_elif_else_while_and_nested_for(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int32:\n'
                '    total: int32 = 0\n'
                '    i: int32 = 0\n'
                '    while i < 3:\n'
                '        if i == 0:\n'
                '            total += 1\n'
                '        elif i == 1:\n'
                '            total += 2\n'
                '        else:\n'
                '            total += 3\n'
                '        i += 1\n'
                '    for outer: uint32 ran (0, 2, 1):\n'
                '        for inner: uint32 ran (0, 2, 1):\n'
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
                'func main() int32:\n'
                '    total: int32 = 0\n'
                '    for i: uint32 ran (0, 3, 1):\n'
                '        j: int32 = 0\n'
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

    def test_builds_and_runs_bool_while_with_break_and_continue(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int32:\n'
                '    total: int32 = 0\n'
                '    running: bool = true\n'
                '    i: int32 = 0\n'
                '    while running:\n'
                '        i += 1\n'
                '        if i == 2:\n'
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

        self.assertEqual(2, result.returncode)

    def test_builds_and_runs_zero_iteration_bool_while(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int32:\n'
                '    entered: bool = false\n'
                '    count: int32 = 0\n'
                '    while entered:\n'
                '        count += 100\n'
                '    return count\n',
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

    def test_builds_and_runs_break_and_continue_in_nested_control_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(
                'func main() int32:\n'
                '    total: int32 = 0\n'
                '    for i: uint32 ran (0, 5, 1):\n'
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
            self.compile_source('base: int32 = 10\ncopy: int32 = base\n')

    def test_rejects_mutable_reference_inside_array(self):
        with self.assertRaisesRegex(CompilationError, 'global mutable base'):
            self.compile_source(
                'base: int32 = 10\n'
                'values: int32[] = {base}\n'
            )

    def test_rejects_invalid_arch(self):
        with self.assertRaisesRegex(CompilationError, 'valor invalido'):
            self.compile_source("clause Arch 'invalid'\nvalue: int32 = 1\n")

    def test_accepts_explicit_llvm_triple(self):
        from llvmlite import binding as llvm

        triple = llvm.get_default_triple()
        module = self.compile_source(
            f"clause Arch '{triple}'\n"
            'value: int32 = 1\n'
        )
        self.assertIn(f'target triple = "{triple}"', module)

    def test_requires_global_main(self):
        with self.assertRaisesRegex(CompilationError, 'funcion global main'):
            self.compile_source('value: int32 = 1\n', add_main=False)

    def test_main_requires_int_without_parameters(self):
        with self.assertRaisesRegex(CompilationError, 'debe retornar int32'):
            self.compile_source(
                'func main() bool:\n'
                '    return true\n',
                add_main=False,
            )

        with self.assertRaisesRegex(CompilationError, 'no puede recibir parametros'):
            self.compile_source(
                'func main(value: int32) int32:\n'
                '    return 0\n',
                add_main=False,
            )


if __name__ == '__main__':
    unittest.main()

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler
from core.frontend.objects import AggregateSymbol, EnumSymbol


class TypeSemanticTests(unittest.TestCase):
    def compile_source(self, source: str, executable: bool = False) -> Compiler:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '_main.bg'
            path.write_text(source, encoding='utf-8')
            compiler = Compiler()
            result = compiler.compile(path, executable=executable)
            if executable:
                self.assertTrue(result.executable.exists())
                completed = subprocess.run(
                    [str(result.executable)],
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(0, completed.returncode)
            return compiler

    def test_int_is_removed_and_target_sized_types_are_explicit(self):
        with self.assertRaisesRegex(CompilationError, 'tipo int fue eliminado'):
            self.compile_source(
                'value: int = 1\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'tipo uint fue eliminado'):
            self.compile_source(
                'value: uint = 1\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        compiler = self.compile_source(
            "clause Arch 'x86'\n"
            'value: usize = 1\n'
            'signed_value: isize = 1\n'
            'func main() int32:\n'
            '    return 0\n'
        )
        self.assertEqual(32, compiler.storage.namespace['value'].type_spec.bit_width)
        self.assertEqual(32, compiler.storage.namespace['signed_value'].type_spec.bit_width)
        self.assertFalse(compiler.storage.namespace['value'].type_spec.signed)
        self.assertTrue(compiler.storage.namespace['signed_value'].type_spec.signed)

    def test_integer_assignment_only_allows_same_sign_widening(self):
        self.compile_source(
            'func main() int32:\n'
            '    narrow: int8 = 1\n'
            '    wide: int16 = narrow\n'
            '    unsigned_narrow: uint8 = 1\n'
            '    unsigned_wide: uint16 = unsigned_narrow\n'
            '    return wide\n'
        )

        with self.assertRaisesRegex(CompilationError, 'no coincide con int8'):
            self.compile_source(
                'wide: int16 = 1\n'
                'narrow: int8 = wide\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'no coincide con int16'):
            self.compile_source(
                'unsigned_value: uint8 = 1\n'
                'signed_value: int16 = unsigned_value\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'no coincide con uint16'):
            self.compile_source(
                'raw: byte = 1\n'
                'number: uint16 = raw\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'no coincide con byte'):
            self.compile_source(
                'number: uint8 = 1\n'
                'raw: byte = number\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'ensanchamiento seguro'):
            self.compile_source(
                'raw: byte = 1\n'
                'number: uint16 = 2\n'
                'result: uint16 = raw + number\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_bit_width_types_are_restricted_to_flags(self):
        with self.assertRaisesRegex(CompilationError, 'solo pueden usarse como campos de flags'):
            self.compile_source(
                'value: Bint<5> = 1\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'solo pueden usarse como campos de flags'):
            self.compile_source(
                'func bad(value: uBint<5>) int32:\n'
                '    return 0\n'
            )

        self.compile_source(
            'flags Permisos uint8:\n'
            '    leer: uBint<1> = 1\n'
            '    modo: Bint<3> = 2\n'
            '    activo: bool = true\n'
            '    reservado: uBint<3> = 0\n'
            'func main() int32:\n'
            '    return 0\n'
        )

        with self.assertRaisesRegex(CompilationError, 'debe usar Bint, uBint o bool'):
            self.compile_source(
                'flags Invalidos uint8:\n'
                '    valor: uint8 = 1\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'Bint.*al menos 2 bits'):
            self.compile_source(
                'flags Invalidos uint8:\n'
                '    valor: Bint<1> = 0\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_registers_enum_aggregates_and_flags(self):
        compiler = self.compile_source(
            'enum Estado int8:\n'
            '    INACTIVO,\n'
            '    ACTIVO = 4,\n'
            '    PAUSADO,\n'
            'struct Punto:\n'
            '    x: int32\n'
            '    y: int8\n'
            '    estado: Estado\n'
            'mold PuntoBase:\n'
            '    punto: Punto\n'
            'flags Permisos uint8:\n'
            '    leer: uBint<1> = 1\n'
            '    escribir: uBint<1> = 0\n'
            '    reservado: uBint<6> = 0\n'
            '\n'
            'func main() int32:\n'
            '    return 0\n'
        )

        enum = compiler.storage.types['Estado']
        self.assertIsInstance(enum, EnumSymbol)
        self.assertEqual('int8', enum.base_type.name)
        self.assertEqual([0, 4, 5], [member.value for member in enum.members])

        point = compiler.storage.types['Punto']
        mold = compiler.storage.types['PuntoBase']
        flags = compiler.storage.types['Permisos']
        self.assertIsInstance(point, AggregateSymbol)
        self.assertIsInstance(mold, AggregateSymbol)
        self.assertIsInstance(flags, AggregateSymbol)
        self.assertEqual('struct', point.kind)
        self.assertEqual('mold', mold.kind)
        self.assertEqual('flags', flags.kind)
        self.assertEqual(['x', 'y', 'estado'], [field.name for field in point.fields])
        self.assertEqual('Estado', point.fields[2].type_spec.name)
        self.assertEqual('Punto', mold.fields[0].type_spec.name)
        self.assertEqual('uint8', flags.base_type.name)
        self.assertEqual([1, 0, 0], [field.value_info.value for field in flags.fields])
        self.assertEqual([0, 1, 2], [field.bit_offset for field in flags.fields])

    def test_rejects_duplicate_members_and_fields(self):
        with self.assertRaisesRegex(CompilationError, 'miembro Estado.ACTIVO'):
            self.compile_source(
                'enum Estado:\n'
                '    ACTIVO,\n'
                '    ACTIVO,\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'fuera del rango'):
            self.compile_source(
                'enum Estado int8:\n'
                '    DEMASIADO_GRANDE = 128,\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'campo Punto.x'):
            self.compile_source(
                'struct Punto:\n'
                '    x: int32\n'
                '    x: int32\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_rejects_unknown_and_invalid_flags_fields(self):
        with self.assertRaisesRegex(CompilationError, 'no existe'):
            self.compile_source(
                'struct Punto:\n'
                '    x: Missing\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'literal entero'):
            self.compile_source(
                'flags Permisos uint8:\n'
                '    leer: uBint<1> = true\n'
                '    reservado: uBint<8> = 0\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'no coincide'):
            self.compile_source(
                'flags Permisos uint8:\n'
                '    leer: uBint<1> = 2\n'
                '    reservado: uBint<8> = 0\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'tipo base'):
            self.compile_source(
                'flags Permisos bool:\n'
                '    leer: uBint<1> = 1\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'debe ser uint8/16/32/64'):
            self.compile_source(
                'flags Permisos int8:\n'
                '    leer: uBint<1> = 1\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'ocupan 2 bits.*exactamente 8'):
            self.compile_source(
                'flags Permisos uint8:\n'
                '    leer: uBint<1> = 1\n'
                '    escribir: uBint<1> = 0\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'ocupan 9 bits'):
            self.compile_source(
                'flags Permisos uint8:\n'
                '    primero: uBint<5> = 0\n'
                '    segundo: uBint<4> = 0\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_rejects_empty_and_recursive_aggregate_layouts(self):
        with self.assertRaisesRegex(CompilationError, 'no puede estar vacio'):
            self.compile_source(
                'mold Vacio:\n'
                '    pass\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'Ciclo de agregados por valor'):
            self.compile_source(
                'struct A:\n'
                '    b: B\n'
                'struct B:\n'
                '    a: A\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_flags_have_no_address_and_mold_pointer_reads_require_unsafe(self):
        with self.assertRaisesRegex(CompilationError, 'no tiene una direccion'):
            self.compile_source(
                'flags Estado uint8:\n'
                '    activo: uBint<1> = 1\n'
                '    reservado: uBint<7> = 0\n'
                'func main() int32:\n'
                '    estado: Estado\n'
                '    bit *: void = $estado.activo\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'procedencia conocida'):
            self.compile_source(
                'mold Vista:\n'
                '    puntero *: int32\n'
                'func leer(vista: Vista) int32:\n'
                '    return (vista.puntero)\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_registers_aggregate_modifiers_and_bit_order(self):
        compiler = self.compile_source(
            '@packed\n'
            '@align(8)\n'
            'struct Paquete:\n'
            '    etiqueta: byte\n'
            '    valor: int32\n'
            'volatile mold Registro:\n'
            '    entero: int64\n'
            '    bytes: byte[8]\n'
            '@order_msb\n'
            'flags Estado uint8:\n'
            '    activo: uBint<1> = 1\n'
            '    modo: uBint<2> = 2\n'
            '    reservado: uBint<5> = 0\n'
            'func main() int32:\n'
            '    return 0\n'
        )

        paquete = compiler.storage.types['Paquete']
        registro = compiler.storage.types['Registro']
        estado = compiler.storage.types['Estado']
        self.assertTrue(paquete.is_packed)
        self.assertEqual(8, paquete.alignment)
        self.assertTrue(registro.is_volatile)
        self.assertEqual('msb', estado.bit_order)
        self.assertEqual([7, 5, 0], [field.bit_offset for field in estado.fields])

    def test_type_definitions_still_build_minimal_executable(self):
        self.compile_source(
            'enum Estado:\n'
            '    LISTO,\n'
            'struct Punto:\n'
            '    x: int32\n'
            'mold Base:\n'
            '    x: int32\n'
            'flags Permisos uint8:\n'
            '    leer: uBint<1> = 1\n'
            '    reservado: uBint<7> = 0\n'
            '\n'
            'func main() int32:\n'
            '    return 0\n',
            executable=True,
        )

    def test_char_byte_and_chain_semantics(self):
        compiler = self.compile_source(
            'nombre: char[10] = "Hola"\n'
            'bytes: byte[6] = "x0x0xb"\n'
            'mensaje: chain = "inmutable"\n'
            'func main() int32:\n'
            '    return 0\n'
        )

        self.assertEqual('char[10]', compiler.storage.namespace['nombre'].type)
        self.assertEqual('byte[6]', compiler.storage.namespace['bytes'].type)
        self.assertTrue(compiler.storage.namespace['mensaje'].value_is_const)

    def test_rejects_invalid_char_byte_and_chain_declarations(self):
        with self.assertRaisesRegex(CompilationError, 'no coincide'):
            self.compile_source(
                'letra: char = 65\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'no coincide'):
            self.compile_source(
                'bytes: byte[5] = "x0x0xb"\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'no coincide'):
            self.compile_source(
                'nombre: char[4] = "Hola"\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'debe tener un inicializador'):
            self.compile_source(
                'mensaje: chain\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'constante no puede asignarse'):
            self.compile_source(
                'func main() int32:\n'
                '    mensaje: chain = "hola"\n'
                '    mensaje = "adios"\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'chain ya es constante'):
            self.compile_source(
                'mensaje: const chain = "hola"\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_requires_data_for_inferred_array_size(self):
        with self.assertRaisesRegex(CompilationError, 'inferir su tamano'):
            self.compile_source(
                'data: int32[]\n'
                'func main() int32:\n'
                '    return 0\n'
            )

        self.compile_source(
            'data: int32[3]\n'
            'func main() int32:\n'
            '    return 0\n'
        )

    def test_infers_char_and_byte_array_sizes_from_strings(self):
        compiler = self.compile_source(
            'nombre: char[] = "Hola"\n'
            'bytes: byte[] = "abc"\n'
            'func main() int32:\n'
            '    return 0\n'
        )

        self.assertEqual('char[5]', compiler.storage.namespace['nombre'].type)
        self.assertEqual('byte[3]', compiler.storage.namespace['bytes'].type)

        compiler = self.compile_source(
            'letras: char[] = {"H", "i"}\n'
            'func main() int32:\n'
            '    return 0\n'
        )
        self.assertEqual('char[3]', compiler.storage.namespace['letras'].type)

    def test_compile_time_char_array_to_chain_conversion(self):
        compiler = self.compile_source(
            'source: const char[5] = "Hola"\n'
            'message: chain = source\n'
            'func main() int32:\n'
            '    return 0\n'
        )
        self.assertTrue(compiler.storage.namespace['message'].value_is_const)

        with self.assertRaisesRegex(CompilationError, 'no coincide'):
            self.compile_source(
                'func bad(value: char) int32:\n'
                '    message: chain = value\n'
                '    return 0\n'
            )


if __name__ == '__main__':
    unittest.main()

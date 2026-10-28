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

    def test_registers_enum_aggregates_and_flags(self):
        compiler = self.compile_source(
            'enum Estado int8:\n'
            '    INACTIVO,\n'
            '    ACTIVO = 4,\n'
            '    PAUSADO,\n'
            'struct Punto:\n'
            '    x: int\n'
            '    y: Bint<5>\n'
            '    estado: Estado\n'
            'mold PuntoBase:\n'
            '    punto: Punto\n'
            'flags Permisos:\n'
            '    leer: uBint<1> = 1\n'
            '    escribir: uBint<1> = 0\n'
            '\n'
            'func main() int:\n'
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
        self.assertEqual([1, 0], [field.value_info.value for field in flags.fields])

    def test_rejects_duplicate_members_and_fields(self):
        with self.assertRaisesRegex(CompilationError, 'miembro Estado.ACTIVO'):
            self.compile_source(
                'enum Estado:\n'
                '    ACTIVO,\n'
                '    ACTIVO,\n'
                'func main() int:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'fuera del rango'):
            self.compile_source(
                'enum Estado int8:\n'
                '    DEMASIADO_GRANDE = 128,\n'
                'func main() int:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'campo Punto.x'):
            self.compile_source(
                'struct Punto:\n'
                '    x: int\n'
                '    x: int\n'
                'func main() int:\n'
                '    return 0\n'
            )

    def test_rejects_unknown_and_invalid_flags_fields(self):
        with self.assertRaisesRegex(CompilationError, 'no existe'):
            self.compile_source(
                'struct Punto:\n'
                '    x: Missing\n'
                'func main() int:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'literal entero'):
            self.compile_source(
                'flags Permisos:\n'
                '    leer: uBint<1> = true\n'
                'func main() int:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'no coincide'):
            self.compile_source(
                'flags Permisos:\n'
                '    leer: uBint<1> = 2\n'
                'func main() int:\n'
                '    return 0\n'
            )

    def test_reports_pending_type_modifiers(self):
        with self.assertRaisesRegex(CompilationError, '@packed'):
            self.compile_source(
                '@packed\n'
                'struct Punto:\n'
                '    x: int\n'
                'func main() int:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'volatile'):
            self.compile_source(
                'volatile struct Punto:\n'
                '    x: int\n'
                'func main() int:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, '__align__'):
            self.compile_source(
                'struct Punto:\n'
                '    __align__ 8\n'
                '    x: int\n'
                'func main() int:\n'
                '    return 0\n'
            )

    def test_type_definitions_still_build_minimal_executable(self):
        self.compile_source(
            'enum Estado:\n'
            '    LISTO,\n'
            'struct Punto:\n'
            '    x: int\n'
            'mold Base:\n'
            '    x: int\n'
            'flags Permisos:\n'
            '    leer: uBint<1> = 1\n'
            '\n'
            'func main() int:\n'
            '    return 0\n',
            executable=True,
        )

    def test_char_byte_and_chain_semantics(self):
        compiler = self.compile_source(
            'nombre: char[10] = "Hola"\n'
            'bytes: byte[6] = "x0x0xb"\n'
            'mensaje: chain = "inmutable"\n'
            'func main() int:\n'
            '    return 0\n'
        )

        self.assertEqual('char[10]', compiler.storage.namespace['nombre'].type)
        self.assertEqual('byte[6]', compiler.storage.namespace['bytes'].type)
        self.assertTrue(compiler.storage.namespace['mensaje'].value_is_const)

    def test_rejects_invalid_char_byte_and_chain_declarations(self):
        with self.assertRaisesRegex(CompilationError, 'no coincide'):
            self.compile_source(
                'letra: char = 65\n'
                'func main() int:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'no coincide'):
            self.compile_source(
                'bytes: byte[5] = "x0x0xb"\n'
                'func main() int:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'debe tener un inicializador'):
            self.compile_source(
                'mensaje: chain\n'
                'func main() int:\n'
                '    return 0\n'
            )

        with self.assertRaisesRegex(CompilationError, 'constante no puede asignarse'):
            self.compile_source(
                'func main() int:\n'
                '    mensaje: chain = "hola"\n'
                '    mensaje = "adios"\n'
                '    return 0\n'
            )

    def test_requires_data_for_inferred_array_size(self):
        with self.assertRaisesRegex(CompilationError, 'inferir su tamano'):
            self.compile_source(
                'data: int[]\n'
                'func main() int:\n'
                '    return 0\n'
            )

        self.compile_source(
            'data: int[3]\n'
            'func main() int:\n'
            '    return 0\n'
        )


if __name__ == '__main__':
    unittest.main()

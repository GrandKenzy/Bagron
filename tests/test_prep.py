from __future__ import annotations

import tempfile
import unittest
import subprocess
from pathlib import Path

from core.compiler import CompilationError, Compiler


class PrepTests(unittest.TestCase):
    def _compile(self, source: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        return Path(Compiler().compile(path, executable=False))

    def test_extracts_raw_assembler_to_function_file(self):
        ir_path = self._compile(
            '@assembler\n'
            'func main() int:\n'
            '    #prep assembler "intel"\n'
            '        mov eax, ebx\n'
            '        nop\n'
            '    #end\n'
            '    return asm\n'
        )

        asm_path = ir_path.parent / 'prep' / '_main' / 'main__prep_0.asm'
        self.assertTrue(asm_path.exists())
        self.assertEqual(
            '.intel_syntax noprefix\n'
            '.text\n'
            '.globl __bagron_main\n'
            '__bagron_main:\n'
            '    mov eax, 1\n'
            '    mov eax, ebx\n'
            '    nop\n'
            '    ret\n',
            asm_path.read_text(encoding='utf-8'),
        )

    def test_rejects_multiple_prep_blocks_in_assembler_function(self):
        with self.assertRaisesRegex(CompilationError, 'solo puede contener un bloque'):
            self._compile(
            '@assembler\n'
            'func main() int:\n'
            '    #prep assembler "intel"\n'
            '        nop\n'
            '    #end\n'
            '    #prep assembler "att"\n'
            '        ret\n'
            '    #end\n'
            '    return asm\n'
            )

    def test_rejects_prep_without_assembler_decorator(self):
        with self.assertRaisesRegex(CompilationError, 'requiere el decorador @assembler'):
            self._compile(
                'func main() int:\n'
                '    #prep assembler "intel"\n'
                '        nop\n'
                '    #end\n'
                '    return 0\n'
            )

    def test_rejects_return_asm_without_assembler_block(self):
        with self.assertRaisesRegex(CompilationError, 'no puede usar return asm'):
            self._compile(
                '@assembler\n'
                'func bad() int:\n'
                '    return asm\n'
                'func main() int:\n'
                '    return 0\n'
            )

    def test_rejects_return_asm_without_assembler_decorator(self):
        with self.assertRaisesRegex(CompilationError, 'requiere el decorador @assembler'):
            self._compile(
                'func bad() int:\n'
                '    return asm\n'
                'func main() int:\n'
                '    return 0\n'
            )

    def test_assembler_function_may_only_have_return_without_prep(self):
        ir_path = self._compile(
            '@assembler\n'
            'func main() int:\n'
            '    return 0\n'
        )
        self.assertTrue(ir_path.exists())

    def test_builds_and_runs_assembler_function_with_status(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            '@assembler\n'
            'func validar(a: int, b: int) int:\n'
            '    #prep assembler "intel"\n'
            '        mov eax, 1\n'
            '        cmp {a}, {b}\n'
            '        jne fallo\n'
            '        xor eax, eax\n'
            '        fallo:\n'
            '    #end\n'
            '    return asm\n'
            'func main() int:\n'
            '    return validar(2, 2)\n',
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
        self.assertTrue(artifacts.prep_objects)
        asm_text = artifacts.prep_sources[0].read_text(encoding='utf-8')
        self.assertIn('cmp ecx, edx', asm_text)

    def test_supports_att_syntax_and_register_placeholders(self):
        ir_path = self._compile(
            '@assembler\n'
            'func main() int:\n'
            '    #prep assembler "att"\n'
            '        xorl %eax, %eax\n'
            '    #end\n'
            '    return asm\n'
        )

        asm_path = ir_path.parent / 'prep' / '_main' / 'main__prep_0.asm'
        asm_text = asm_path.read_text(encoding='utf-8')
        self.assertIn('.att_syntax prefix', asm_text)
        self.assertIn('movl $1, %eax', asm_text)
        self.assertIn('xorl %eax, %eax', asm_text)

    def test_infers_register_aliases_from_parameter_width(self):
        ir_path = self._compile(
            '@assembler\n'
            'func widths(a: int8, b: int16, c: int32, d: int64) int:\n'
            '    #prep assembler "intel"\n'
            '        mov al, {a}\n'
            '        mov dx, {b}\n'
            '        mov r8d, {c}\n'
            '        mov r9, {d}\n'
            '    #end\n'
            '    return asm\n'
            'func main() int:\n'
            '    return 0\n'
        )

        asm_path = ir_path.parent / 'prep' / '_main' / 'widths__prep_0.asm'
        asm_text = asm_path.read_text(encoding='utf-8')
        self.assertIn('mov al, cl', asm_text)
        self.assertIn('mov dx, dx', asm_text)
        self.assertIn('mov r8d, r8d', asm_text)
        self.assertIn('mov r9, r9', asm_text)

    def test_maps_pointer_parameter_to_full_abi_register(self):
        ir_path = self._compile(
            '@assembler\n'
            'func read(pointer *: int) int:\n'
            '    #prep assembler "intel"\n'
            '        mov eax, [{pointer}]\n'
            '    #end\n'
            '    return asm\n'
            'func main() int:\n'
            '    return 0\n'
        )

        asm_path = ir_path.parent / 'prep' / '_main' / 'read__prep_0.asm'
        self.assertIn('mov eax, [rcx]', asm_path.read_text(encoding='utf-8'))

    def test_assembler_defaults_to_failure_status(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            '@assembler\n'
            'func fallo() int:\n'
            '    #prep assembler "intel"\n'
            '        nop\n'
            '    #end\n'
            '    return asm\n'
            'func main() int:\n'
            '    return fallo()\n',
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

    def test_rejects_regular_statements_in_assembler_function(self):
        with self.assertRaisesRegex(CompilationError, 'solo puede contener'):
            self._compile(
                '@assembler\n'
                'func main() int:\n'
                '    result: int = 1\n'
                '    return result\n'
            )

    def test_rejects_unknown_template_parameter(self):
        with self.assertRaisesRegex(CompilationError, 'parametro ASM no existe'):
            self._compile(
                '@assembler\n'
                'func bad(value: int) int:\n'
                '    #prep assembler "intel"\n'
                '        mov eax, {missing}\n'
                '    #end\n'
                '    return asm\n'
                'func main() int:\n'
                '    return 0\n'
            )

    def test_rejects_unsupported_assembler_dialect(self):
        with self.assertRaisesRegex(CompilationError, 'usa "intel" o "att"'):
            self._compile(
                '@assembler\n'
                'func bad() int:\n'
                '    #prep assembler "nasm"\n'
                '        xor eax, eax\n'
                '    #end\n'
                '    return asm\n'
                'func main() int:\n'
                '    return 0\n'
            )

    def test_maps_fifth_assembler_parameter_to_windows_stack(self):
        ir_path = self._compile(
            '@assembler\n'
            'func stack(a: int, b: int, c: int, d: int, e: int) int:\n'
            '    #prep assembler "intel"\n'
            '        mov eax, {e}\n'
            '    #end\n'
            '    return asm\n'
            'func main() int:\n'
            '    return stack(1, 2, 3, 4, 5)\n'
        )

        asm_path = ir_path.parent / 'prep' / '_main' / 'stack__prep_0.asm'
        asm_text = asm_path.read_text(encoding='utf-8')
        self.assertIn('mov eax, [rsp + 0x28]', asm_text)

    def test_runs_att_assembler_function(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            '@assembler\n'
            'func estado(a: int8) int:\n'
            '    #prep assembler "att"\n'
            '        xorl %eax, %eax\n'
            '        testb {a}, {a}\n'
            '        jne fallo\n'
            '        jmp fin\n'
            '        fallo:\n'
            '        movl $1, %eax\n'
            '        fin:\n'
            '    #end\n'
            '    return asm\n'
            'func main() int:\n'
            '    return estado(0)\n',
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

    def test_runs_assembler_function_with_fifth_stack_parameter(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            '@assembler\n'
            'func quinto(a: int, b: int, c: int, d: int, e: int) int:\n'
            '    #prep assembler "intel"\n'
            '        mov eax, {e}\n'
            '    #end\n'
            '    return asm\n'
            'func main() int:\n'
            '    return quinto(1, 2, 3, 4, 5)\n',
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

    def test_rejects_prep_outside_function(self):
        with self.assertRaisesRegex(CompilationError, 'solo se permite dentro de una funcion'):
            self._compile(
                '#prep assembler "intel"\n'
                'mov eax, ebx\n'
                '#end\n'
                'func main() int:\n'
                '    return 0\n'
            )

    def test_rejects_unclosed_prep(self):
        with self.assertRaisesRegex(CompilationError, 'no tiene un #end de cierre'):
            self._compile(
                'func main() int:\n'
                '    #prep assembler "intel"\n'
                '        nop\n'
            )


if __name__ == '__main__':
    unittest.main()

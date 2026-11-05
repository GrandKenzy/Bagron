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

    def test_conditional_preprocessor_filters_inactive_source_before_parser(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            'clause System "windows"\n'
            'clause Arch "amd"\n'
            '#if OS, "windows"\n'
            'func main() int32:\n'
            '    return 0\n'
            '#else\n'
            'this is not Bagron and must never reach Gram\n'
            '#end\n',
            encoding='utf-8',
        )

        ir_path = Compiler().compile(path, executable=False)

        self.assertTrue(ir_path.exists())

    def test_extracts_raw_assembler_to_function_file(self):
        ir_path = self._compile(
            '@assembler\n'
            'func main() int32:\n'
            '    #assembler "intel"\n'
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

    def test_rejects_multiple_assembler_blocks_in_function(self):
        with self.assertRaisesRegex(CompilationError, 'solo puede contener un bloque'):
            self._compile(
            '@assembler\n'
            'func main() int32:\n'
            '    #assembler "intel"\n'
            '        nop\n'
            '    #end\n'
            '    #assembler "att"\n'
            '        ret\n'
            '    #end\n'
            '    return asm\n'
            )

    def test_rejects_assembler_without_assembler_decorator(self):
        with self.assertRaisesRegex(CompilationError, 'requiere el decorador @assembler'):
            self._compile(
                'func main() int32:\n'
                '    #assembler "intel"\n'
                '        nop\n'
                '    #end\n'
                '    return 0\n'
            )

    def test_rejects_return_asm_without_assembler_block(self):
        with self.assertRaisesRegex(CompilationError, 'no puede usar return asm'):
            self._compile(
                '@assembler\n'
                'func bad() int32:\n'
                '    return asm\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_rejects_return_asm_without_assembler_decorator(self):
        with self.assertRaisesRegex(CompilationError, 'requiere el decorador @assembler'):
            self._compile(
                'func bad() int32:\n'
                '    return asm\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_assembler_function_may_only_have_return_without_block(self):
        ir_path = self._compile(
            '@assembler\n'
            'func main() int32:\n'
            '    return 0\n'
        )
        self.assertTrue(ir_path.exists())

    def test_void_assembler_function_does_not_require_return_asm(self):
        ir_path = self._compile(
            '@assembler\n'
            'func helper() void:\n'
            '    #assembler "intel"\n'
            '        nop\n'
            '    #end\n'
            'func main() int32:\n'
            '    return 0\n'
        )

        asm_path = ir_path.parent / 'prep' / '_main' / 'helper__prep_0.asm'
        asm_text = asm_path.read_text(encoding='utf-8')
        self.assertIn('.intel_syntax noprefix\n.text\n.globl ', asm_text)
        self.assertIn('    nop\n    ret\n', asm_text)

    def test_runs_void_assembler_function_without_return_asm(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            '@assembler\n'
            'func helper() void:\n'
            '    #assembler "intel"\n'
            '        nop\n'
            '    #end\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    helper()\n'
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

    def test_builds_and_runs_assembler_function_with_status(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            '@assembler\n'
            'func validar(a: int32, b: int32) int32:\n'
            '    #assembler "intel"\n'
            '        mov eax, 1\n'
            '        cmp ecx, edx\n'
            '        jne fallo\n'
            '        xor eax, eax\n'
            '        fallo:\n'
            '    #end\n'
            '    return asm\n'
            '@unsafe\n'
            'func main() int32:\n'
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

    def test_supports_att_syntax_without_register_placeholders(self):
        ir_path = self._compile(
            '@assembler\n'
            'func main() int32:\n'
            '    #assembler "att"\n'
            '        xorl %eax, %eax\n'
            '    #end\n'
            '    return asm\n'
        )

        asm_path = ir_path.parent / 'prep' / '_main' / 'main__prep_0.asm'
        asm_text = asm_path.read_text(encoding='utf-8')
        self.assertIn('.att_syntax prefix', asm_text)
        self.assertIn('movl $1, %eax', asm_text)
        self.assertIn('xorl %eax, %eax', asm_text)

    def test_rejects_legacy_gas_intel_dialect(self):
        with self.assertRaisesRegex(CompilationError, 'gas-intel.*retirado'):
            self._compile(
                '@assembler\n'
                'func main() int32:\n'
                '    #assembler "gas-intel"\n'
                '        xor eax, eax\n'
                '    #end\n'
                '    return asm\n'
            )

    def test_rejects_legacy_prep_directive(self):
        with self.assertRaisesRegex(CompilationError, 'directiva #prep fue retirada'):
            self._compile(
                '@assembler\n'
                'func main() int32:\n'
                '    #prep assembler "intel"\n'
                '        xor eax, eax\n'
                '    #end\n'
                '    return asm\n'
            )

    def test_preserves_direct_abi_registers_for_parameter_widths(self):
        ir_path = self._compile(
            '@assembler\n'
            'func widths(a: int8, b: int16, c: int32, d: int64) int32:\n'
            '    #assembler "intel"\n'
            '        mov al, cl\n'
            '        mov dx, dx\n'
            '        mov r8d, r8d\n'
            '        mov r9, r9\n'
            '    #end\n'
            '    return asm\n'
            'func main() int32:\n'
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
            'func read(pointer *: int32) int32:\n'
            '    #assembler "intel"\n'
            '        mov eax, [rcx]\n'
            '    #end\n'
            '    return asm\n'
            'func main() int32:\n'
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
            'func fallo() int32:\n'
            '    #assembler "intel"\n'
            '        nop\n'
            '    #end\n'
            '    return asm\n'
            '@unsafe\n'
            'func main() int32:\n'
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
                'func main() int32:\n'
                '    result: int32 = 1\n'
                '    return result\n'
            )

    def test_preserves_legacy_placeholder_text_without_expanding_it(self):
        ir_path = self._compile(
            '@assembler\n'
            'func bad(value: int32) int32:\n'
            '    #assembler "intel"\n'
            '        # {missing}\n'
            '        xor eax, eax\n'
            '    #end\n'
            '    return asm\n'
            'func main() int32:\n'
            '    return 0\n'
        )
        asm_path = ir_path.parent / 'prep' / '_main' / 'bad__prep_0.asm'
        self.assertIn('# {missing}', asm_path.read_text(encoding='utf-8'))

    def test_rejects_unsupported_assembler_dialect(self):
        with self.assertRaisesRegex(CompilationError, 'dialecto NASM'):
            self._compile(
                '@assembler\n'
                'func bad() int32:\n'
            '    #assembler "nasm"\n'
                '        xor eax, eax\n'
                '    #end\n'
                '    return asm\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_maps_fifth_assembler_parameter_to_windows_stack(self):
        ir_path = self._compile(
            '@assembler\n'
            'func stack(a: int32, b: int32, c: int32, d: int32, e: int32) int32:\n'
            '    #assembler "intel"\n'
            '        mov eax, [rsp + 0x28]\n'
            '    #end\n'
            '    return asm\n'
            '@unsafe\n'
            'func main() int32:\n'
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
            'func estado(a: int8) int32:\n'
            '    #assembler "att"\n'
            '        xorl %eax, %eax\n'
            '        testb %cl, %cl\n'
            '        jne fallo\n'
            '        jmp fin\n'
            '        fallo:\n'
            '        movl $1, %eax\n'
            '        fin:\n'
            '    #end\n'
            '    return asm\n'
            '@unsafe\n'
            'func main() int32:\n'
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
            'func quinto(a: int32, b: int32, c: int32, d: int32, e: int32) int32:\n'
            '    #assembler "intel"\n'
            '        mov eax, [rsp + 0x28]\n'
            '    #end\n'
            '    return asm\n'
            '@unsafe\n'
            'func main() int32:\n'
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

    def test_baremetal_assembler_uses_explicit_sysv_abi(self):
        ir_path = self._compile(
            'clause System "baremetal"\n'
            'clause Arch "amd"\n'
            'clause Boot "none"\n'
            'clause ABI "sysv_amd64"\n'
            '@assembler\n'
            'func identity(value: int32) int32:\n'
            '    #assembler "att"\n'
            '        movl %edi, %eax\n'
            '    #end\n'
            '    return asm\n'
            'func main() int32:\n'
            '    return 0\n'
        )

        asm_path = ir_path.parent / 'prep' / '_main' / 'identity__prep_0.asm'
        asm_text = asm_path.read_text(encoding='utf-8')
        self.assertIn('.att_syntax prefix', asm_text)
        self.assertIn('movl %edi, %eax', asm_text)

    def test_baremetal_assembler_can_be_called_from_an_imported_module(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / 'modules').mkdir()
        (root / 'modules' / 'asm_module.bg').write_text(
            '@assembler\n'
            'public func identity(value: int32) int32:\n'
            '    #assembler "att"\n'
            '        movl %edi, %eax\n'
            '    #end\n'
            '    return asm\n',
            encoding='utf-8',
        )
        main = root / '_main.bg'
        main.write_text(
            'clause System "baremetal"\n'
            'clause Arch "amd"\n'
            'clause Boot "none"\n'
            'clause ABI "sysv_amd64"\n'
            'import asm_module\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    return asm_module.identity(7)\n',
            encoding='utf-8',
        )

        compiler = Compiler()
        ir_path = Path(compiler.compile(main, executable=False))
        self.assertTrue(ir_path.exists())
        self.assertEqual(1, len(compiler.storage.prep_sources))
        ir_text = ir_path.read_text(encoding='utf-8')
        self.assertRegex(ir_text, r'call i32 .*identity')

    def test_rejects_assembler_outside_function(self):
        with self.assertRaisesRegex(CompilationError, 'solo se permite dentro de una funcion'):
            self._compile(
                '#assembler "intel"\n'
                'mov eax, ebx\n'
                '#end\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_rejects_module_assembler_block(self):
        with self.assertRaisesRegex(CompilationError, 'se esperaba #assembler'):
            self._compile(
                '#assembler module "intel"\n'
                '    nop\n'
                '#end\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_rejects_unclosed_assembler_block(self):
        with self.assertRaisesRegex(CompilationError, 'no tiene un #end de cierre'):
            self._compile(
                'func main() int32:\n'
                '    #assembler "intel"\n'
                '        nop\n'
            )


if __name__ == '__main__':
    unittest.main()


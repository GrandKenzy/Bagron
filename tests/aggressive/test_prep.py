from __future__ import annotations

import os
import tempfile
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch

from core.backend.llvm.module import LLVMBackend
from core.compiler import CompilationError, Compiler
from core.compiler.prep import PrepBlockMetadata


WINDOWS_ONLY = unittest.skipUnless(
    os.name == 'nt', 'the test uses the Windows ABI'
)


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

    def test_extracts_raw_assembler_to_source_file(self):
        ir_path = self._compile(
            '@assembler\n'
            'func main() int32:\n'
            '    #assembler "intel"\n'
            '        mov eax, ebx\n'
            '        nop\n'
            '    #end\n'
            '    return asm\n'
        )

        asm_path = ir_path.parent / 'prep' / '_main' / '_main__prep.asm'
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

    def test_groups_assembler_functions_from_one_source(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            '@assembler\n'
            'func first() int32:\n'
            '    #assembler "intel"\n'
            '        mov eax, 11\n'
            '    #end\n'
            '    return asm\n'
            '@assembler\n'
            'func second() int32:\n'
            '    #assembler "att"\n'
            '        movl $22, %eax\n'
            '    #end\n'
            '    return asm\n'
            'func main() int32:\n'
            '    return 0\n',
            encoding='utf-8',
        )

        compiler = Compiler()
        artifacts = compiler.compile(path)

        self.assertEqual(1, len(compiler.storage.prep_sources))
        self.assertEqual(1, len(artifacts.prep_objects))
        asm_path = compiler.storage.prep_sources[0]
        self.assertEqual('_main__prep.asm', asm_path.name)
        self.assertEqual(
            ['first', 'second'],
            [item.function_name for item in compiler.storage.prep_metadata[asm_path]],
        )
        asm_text = asm_path.read_text(encoding='utf-8')
        self.assertEqual(2, asm_text.count('.globl '))
        self.assertIn('mov eax, 11', asm_text)
        self.assertIn('movl $22, %eax', asm_text)
        self.assertLess(asm_text.index('mov eax, 11'), asm_text.index('movl $22, %eax'))

    def test_assembles_once_per_grouped_source_unit(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        main_source = root / '_main__prep.asm'
        helper_source = root / 'helper__prep.asm'
        main_source.write_text('nop\n', encoding='utf-8')
        helper_source.write_text('nop\n', encoding='utf-8')

        result = subprocess.CompletedProcess([], 0, stdout='', stderr='')
        with patch(
            'core.backend.llvm.module.subprocess.run',
            return_value=result,
        ) as run:
            objects = LLVMBackend._assemble_prep_sources(
                [main_source, helper_source],
                'x86_64-pc-windows-msvc',
            )

        self.assertEqual(2, run.call_count)
        self.assertEqual([main_source.with_suffix('.obj'), helper_source.with_suffix('.obj')], objects)

    def test_cleans_grouped_and_legacy_prep_artifacts_without_assembler(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            '@assembler\n'
            'func helper() int32:\n'
            '    #assembler "intel"\n'
            '        mov eax, 1\n'
            '    #end\n'
            '    return asm\n'
            'func main() int32:\n'
            '    return 0\n',
            encoding='utf-8',
        )

        Compiler().compile(path, executable=False)
        prep_root = path.parent / 'build' / 'prep'
        prep_dir = prep_root / '_main'
        for name in (
            'old__prep_0.asm',
            'old__prep_0.obj',
            'old__prep_0.o',
            'stale__prep.asm',
            'stale__prep.obj',
            'stale__prep.o',
        ):
            (prep_dir / name).write_text('stale', encoding='utf-8')

        path.write_text('func main() int32:\n    return 0\n', encoding='utf-8')
        Compiler().compile(path, executable=False)

        self.assertFalse(any(prep_root.rglob('*__prep*')))

    def test_rejects_repeated_non_local_assembler_labels(self):
        with self.assertRaisesRegex(CompilationError, 'etiqueta ASM no local.*shared.*first'):
            self._compile(
                '@assembler\n'
                'func first() int32:\n'
                '    #assembler "intel"\n'
                '        shared:\n'
                '        mov eax, 1\n'
                '    #end\n'
                '    return asm\n'
                '@assembler\n'
                'func second() int32:\n'
                '    #assembler "intel"\n'
                '        shared:\n'
                '        mov eax, 2\n'
                '    #end\n'
                '    return asm\n'
                'func main() int32:\n'
                '    return 0\n'
            )

    def test_allows_repeated_local_assembler_labels(self):
        compiler = Compiler()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            '@assembler\n'
            'func first() int32:\n'
            '    #assembler "intel"\n'
            '        .Ldone:\n'
            '        mov eax, 1\n'
            '    #end\n'
            '    return asm\n'
            '@assembler\n'
            'func second() int32:\n'
            '    #assembler "intel"\n'
            '        .Ldone:\n'
            '        mov eax, 2\n'
            '    #end\n'
            '    return asm\n'
            'func main() int32:\n'
            '    return 0\n',
            encoding='utf-8',
        )

        compiler.compile(path, executable=False)
        self.assertEqual(1, len(compiler.storage.prep_sources))

    def test_keeps_imported_assembler_sources_in_separate_units(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / 'modules').mkdir()
        (root / 'modules' / 'helper.bg').write_text(
            '@assembler\n'
            'public func helper() int32:\n'
            '    #assembler "intel"\n'
            '        mov eax, 7\n'
            '    #end\n'
            '    return asm\n',
            encoding='utf-8',
        )
        main = root / '_main.bg'
        main.write_text(
            'import helper\n'
            '@assembler\n'
            'func main() int32:\n'
            '    #assembler "att"\n'
            '        xorl %eax, %eax\n'
            '    #end\n'
            '    return asm\n',
            encoding='utf-8',
        )

        compiler = Compiler()
        compiler.compile(main, executable=False)

        self.assertEqual(2, len(compiler.storage.prep_sources))
        self.assertEqual(
            {'_main__prep.asm', 'helper__prep.asm'},
            {path.name for path in compiler.storage.prep_sources},
        )

    def test_maps_clang_error_to_second_grouped_assembler_function(self):
        metadata = (
            PrepBlockMetadata(
                source=Path('first.bg'),
                function_name='first',
                dialect='intel',
                line=4,
                generated_start=1,
                generated_body_start=5,
                generated_body_end=5,
                generated_end=7,
            ),
            PrepBlockMetadata(
                source=Path('second.bg'),
                function_name='second',
                dialect='att',
                line=12,
                generated_start=8,
                generated_body_start=12,
                generated_body_end=12,
                generated_end=14,
            ),
        )

        detail = 'unit__prep.asm:12:3: error: invalid instruction'
        formatted = LLVMBackend._format_assembler_diagnostic(
            Path('unit__prep.asm'),
            detail,
            metadata,
        )

        self.assertIn('second.bg:13:', formatted)
        self.assertIn('funcion @assembler second', formatted)
        self.assertIn('dialecto att', formatted)
        self.assertIn('generado desde unit__prep.asm', formatted)

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

        asm_path = ir_path.parent / 'prep' / '_main' / '_main__prep.asm'
        asm_text = asm_path.read_text(encoding='utf-8')
        self.assertIn('.intel_syntax noprefix\n.text\n.globl ', asm_text)
        self.assertIn('    nop\n    ret\n', asm_text)

    def test_never_assembler_function_does_not_get_implicit_return(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            '@assembler\n'
            'func stop() Never:\n'
            '    #assembler "intel"\n'
            '        ud2\n'
            '    #end\n'
            'func main() int32:\n'
            '    return 0\n',
            encoding='utf-8',
        )

        compiler = Compiler()
        ir_path = Path(compiler.compile(path, executable=False))
        asm_text = compiler.storage.prep_sources[0].read_text(encoding='utf-8')

        self.assertRegex(asm_text, r'\.globl .*_fn_stop_.*\n.*_fn_stop_.*:')
        self.assertIn('    ud2\n', asm_text)
        self.assertNotIn('\n    ret\n', asm_text)
        self.assertNotIn('mov eax, 1', asm_text)
        self.assertIn('declare void', ir_path.read_text(encoding='utf-8'))

    def test_never_assembler_call_emits_void_unreachable_in_llvm(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(
            '@assembler\n'
            'func stop() Never:\n'
            '    #assembler "intel"\n'
            '        ud2\n'
            '    #end\n'
            '@unsafe\n'
            'func main() int32:\n'
            '    stop()\n'
            '    return 0\n',
            encoding='utf-8',
        )

        ir_path = Path(Compiler().compile(path, executable=False))
        ir_text = ir_path.read_text(encoding='utf-8')

        self.assertRegex(ir_text, r'call void .*stop.*\n\s*unreachable')

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

    @WINDOWS_ONLY
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

        asm_path = ir_path.parent / 'prep' / '_main' / '_main__prep.asm'
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

    @WINDOWS_ONLY
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

        asm_path = ir_path.parent / 'prep' / '_main' / '_main__prep.asm'
        asm_text = asm_path.read_text(encoding='utf-8')
        self.assertIn('mov al, cl', asm_text)
        self.assertIn('mov dx, dx', asm_text)
        self.assertIn('mov r8d, r8d', asm_text)
        self.assertIn('mov r9, r9', asm_text)

    @WINDOWS_ONLY
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

        asm_path = ir_path.parent / 'prep' / '_main' / '_main__prep.asm'
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
        asm_path = ir_path.parent / 'prep' / '_main' / '_main__prep.asm'
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

    @WINDOWS_ONLY
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

        asm_path = ir_path.parent / 'prep' / '_main' / '_main__prep.asm'
        asm_text = asm_path.read_text(encoding='utf-8')
        self.assertIn('mov eax, [rsp + 0x28]', asm_text)

    @WINDOWS_ONLY
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

    @WINDOWS_ONLY
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

        asm_path = ir_path.parent / 'prep' / '_main' / '_main__prep.asm'
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


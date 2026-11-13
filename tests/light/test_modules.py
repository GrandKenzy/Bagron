from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler
from core.frontend.tools.imports import resolve_module_path


class ModuleTests(unittest.TestCase):
    def test_modules_directory_is_the_canonical_bg_search_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'modules').mkdir()
            (root / 'modules' / 'math.bg').write_text(
                'public func doble(value: int32) int32:\n'
                '    return value + value\n',
                encoding='utf-8',
            )
            main = root / 'main.bg'
            main.write_text(
                'import math\n'
                'func main() int32:\n'
                '    return math.doble(3)\n',
                encoding='utf-8',
            )

            module = Path(Compiler().compile(main, executable=False)).read_text(
                encoding='utf-8'
            )

        self.assertRegex(module, r'call i32 @"?__bg_[^"\s]*_doble_[^"\s]*"?\(i32 3\)')

    def test_nested_module_folders_are_visual_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            modules = root / 'modules'
            (modules / 'ui' / 'rendering').mkdir(parents=True)
            (modules / 'ui' / 'widgets.bg').write_text(
                'public func value() int32:\n'
                '    return 7\n',
                encoding='utf-8',
            )
            (modules / 'ui' / 'rendering' / 'draw.bg').write_text(
                'import widgets\n'
                'public func draw() int32:\n'
                '    return widgets.value()\n',
                encoding='utf-8',
            )
            main = root / 'main.bg'
            main.write_text(
                'import draw\n'
                'func main() int32:\n'
                '    return draw.draw()\n',
                encoding='utf-8',
            )

            compiler = Compiler()
            output = compiler.compile(main, executable=False)
            loaded = {Path(path).resolve() for path in compiler.storage.loaded_modules}
            module_text = Path(output).read_text(encoding='utf-8')

        self.assertIn((modules / 'ui' / 'widgets.bg').resolve(), loaded)
        self.assertIn((modules / 'ui' / 'rendering' / 'draw.bg').resolve(), loaded)
        self.assertRegex(
            module_text,
            r'call i32 @"?__bg_[^"\s]*_draw_[^"\s]*"?\(\)',
        )

    def test_nested_module_name_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'modules' / 'left').mkdir(parents=True)
            (root / 'modules' / 'right').mkdir(parents=True)
            for folder, value in (('left', 1), ('right', 2)):
                (root / 'modules' / folder / 'shared.bg').write_text(
                    f'public func value() int32:\n    return {value}\n',
                    encoding='utf-8',
                )
            main = root / 'main.bg'
            main.write_text(
                'import shared\n'
                'func main() int32:\n'
                '    return shared.value()\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'modulo .*ambiguo'):
                Compiler().compile(main, executable=False)

    def test_libs_directory_is_not_a_bg_module_search_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'libs').mkdir()
            (root / 'libs' / 'hidden.bg').write_text(
                'public func hidden() int32:\n'
                '    return 7\n',
                encoding='utf-8',
            )
            main = root / 'main.bg'
            main.write_text(
                'import hidden\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'No se encontro el modulo'):
                Compiler().compile(main, executable=False)

    def test_main_link_directories_are_recorded_without_global_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bins').mkdir()
            main = root / '_main.bg'
            main.write_text(
                '#link "./bins"\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            compiler = Compiler()
            compiler.compile(main, executable=False)

        self.assertEqual([(root / 'bins').resolve()], compiler.storage.native_link_dirs)

    def test_entry_module_selects_the_optimization_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'library.bg').write_text(
                "clause Optimizations 'high'\n"
                'public func value() uint32:\n'
                '    return 3\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                "clause Optimizations 'dev'\n"
                'import library\n'
                'func main() int32:\n'
                '    for i: uint32 ran (0, library.value(), 1):\n'
                '        pass\n'
                '    return 0\n',
                encoding='utf-8',
            )

            module = Path(Compiler().compile(main, executable=False)).read_text(
                encoding='utf-8'
            )

        self.assertIn('i.addr', module)

    def test_import_loads_bagron_module_before_main(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'math.bg').write_text(
                'func doble(value: int32) int32:\n'
                '    return value + value\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                "clause Optimizations 'dev'\n"
                'import math\n'
                'func main() int32:\n'
                '    return math.doble(3)\n',
                encoding='utf-8',
            )

            compiler = Compiler()
            output = compiler.compile(main, executable=False)
            module = Path(output).read_text(encoding='utf-8')

        self.assertRegex(module, r'define i32 @"?__bg_[^"\s]*_doble_[^"\s]*"?\(')
        self.assertRegex(module, r'call i32 @"?__bg_[^"\s]*_doble_[^"\s]*"?\(i32 3\)')
        self.assertEqual(2, len(compiler.storage.loaded_modules))

    def test_plain_import_does_not_expose_unqualified_symbol(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'math.bg').write_text(
                'func doble(value: int32) int32:\n'
                '    return value + value\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import math\n'
                'func main() int32:\n'
                '    return doble(3)\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'funcion no existe'):
                Compiler().compile(main, executable=False)

    def test_import_reports_missing_module(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'import missing\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'No se encontro el modulo'):
                Compiler().compile(main, executable=False)

    def test_import_alias_calls_qualified_function(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'math.bg').write_text(
                'func doble(value: int32) int32:\n'
                '    return value + value\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                "clause Optimizations 'dev'\n"
                'import math as m\n'
                'func main() int32:\n'
                '    return m.doble(3)\n',
                encoding='utf-8',
            )

            module_path = Compiler().compile(main, executable=False)
            module = Path(module_path).read_text(encoding='utf-8')

        self.assertRegex(module, r'call i32 @"?__bg_[^"\s]*_doble_[^"\s]*"?\(i32 3\)')

    def test_import_selective_alias_calls_function(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'math.bg').write_text(
                'func doble(value: int32) int32:\n'
                '    return value + value\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                "clause Optimizations 'dev'\n"
                'import { doble as twice } from math\n'
                'func main() int32:\n'
                '    return twice(3)\n',
                encoding='utf-8',
            )

            module_path = Compiler().compile(main, executable=False)
            module = Path(module_path).read_text(encoding='utf-8')

        self.assertRegex(module, r'call i32 @"?__bg_[^"\s]*_doble_[^"\s]*"?\(i32 3\)')

    def test_imported_public_const_global_is_readable_without_global(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sdl_init.bg').write_text(
                'public SDL_INIT_AUDIO: const uint32 = 0x00000010\n'
                'public SDL_INIT_VIDEO: const uint32 = 0x00000020\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import { SDL_INIT_AUDIO, SDL_INIT_VIDEO } from sdl_init\n'
                'func main() int32:\n'
                '    if SDL_INIT_AUDIO == 16 && SDL_INIT_VIDEO == 32:\n'
                '        return 0\n'
                '    return 1\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)

    def test_imported_public_const_can_initialize_another_const_global(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sdl_init.bg').write_text(
                'public SDL_INIT_AUDIO: const uint32 = 0x00000010\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import { SDL_INIT_AUDIO as AUDIO } from sdl_init\n'
                'public COPY: const uint32 = AUDIO\n'
                'func main() int32:\n'
                '    if COPY == 16:\n'
                '        return 0\n'
                '    return 1\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)

    def test_imported_public_const_is_readable_through_module_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sdl_init.bg').write_text(
                'public SDL_INIT_AUDIO: const uint32 = 0x00000010\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import sdl_init\n'
                'func main() int32:\n'
                '    if sdl_init.SDL_INIT_AUDIO == 16:\n'
                '        return 0\n'
                '    return 1\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)

    def test_imported_public_mutable_global_is_visible_without_global(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'state.bg').write_text(
                'public value: uint32 = 7\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import { value } from state\n'
                'func main() int32:\n'
                '    if value == 7:\n'
                '        return 0\n'
                '    return 1\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)

    def test_global_statement_is_no_longer_valid_syntax(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'value: int32 = 7\n'
                'func main() int32:\n'
                '    global value\n'
                '    return value\n',
                encoding='utf-8',
            )

            with self.assertRaises(CompilationError):
                Compiler().compile(main, executable=False)

    def test_qualified_imported_mutable_global_can_be_updated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'state.bg').write_text(
                'public value: int32 = 7\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import state\n'
                'func main() int32:\n'
                '    state.value = 8\n'
                '    if state.value == 8:\n'
                '        return 0\n'
                '    return 1\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)

    def test_selective_import_calls_multiple_specific_symbols(self):
        """A selective import binds each requested alias to its source symbol."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'math.bg').write_text(
                'func doble(value: int32) int32:\n'
                '    return value + value\n'
                'func triple(value: int32) int32:\n'
                '    return value + value + value\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                "clause Optimizations 'dev'\n"
                'import { doble as n, triple as t } from math\n'
                'func main() int32:\n'
                '    return n(2) + t(2)\n',
                encoding='utf-8',
            )

            module_path = Compiler().compile(main, executable=False)
            module = Path(module_path).read_text(encoding='utf-8')

        self.assertRegex(module, r'call i32 @"?__bg_[^"\s]*_doble_[^"\s]*"?\(i32 2\)')
        self.assertRegex(module, r'call i32 @"?__bg_[^"\s]*_triple_[^"\s]*"?\(i32 2\)')

    def test_selective_import_rejects_private_symbol(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'hidden.bg').write_text(
                'private func secret() int32:\n'
                '    return 7\n'
                'public func visible() int32:\n'
                '    return 9\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import { secret as exposed } from hidden\n'
                'func main() int32:\n'
                '    return exposed()\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'no es publico'):
                Compiler().compile(main, executable=False)

    def test_imported_alias_preserves_array_expansion_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'arrays.bg').write_text(
                'func total(values: int32[], length: Len_t, size: Size_t) int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                "clause Optimizations 'dev'\n"
                'import arrays as a\n'
                'func main() int32:\n'
                '    values: int32[3] = {1, 2, 3}\n'
                '    return a.total(values)\n',
                encoding='utf-8',
            )

            module_path = Compiler().compile(main, executable=False)
            module = Path(module_path).read_text(encoding='utf-8')

        self.assertRegex(module, r'define i32 @"?__bg_[^"\s]*_total_[^"\s]*"?\(')
        self.assertRegex(module, r'call i32 @"?__bg_[^"\s]*_total_[^"\s]*"?\([^)]*i64 3, i64 4\)')

    def test_private_function_is_not_visible_through_flattened_import_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'hidden.bg').write_text(
                'private func secret() int32:\n'
                '    return 7\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import hidden\n'
                'func main() int32:\n'
                '    return secret()\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'funcion no existe'):
                Compiler().compile(main, executable=False)

    def test_private_global_is_not_visible_inside_importing_function(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'hidden.bg').write_text(
                'private secret: int32 = 7\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import hidden\n'
                'func main() int32:\n'
                '    return secret\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'variable global no existe'):
                Compiler().compile(main, executable=False)

    def test_private_class_is_not_constructible_from_importer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'hidden.bg').write_text(
                'private class Hidden:\n'
                '    func __init__() void:\n'
                '        return\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import hidden\n'
                'func main() int32:\n'
                '    value: Hidden = Hidden()\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'funcion no existe'):
                Compiler().compile(main, executable=False)

    def test_import_rejects_path_like_module_names_even_when_called_directly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / '_main.bg'
            main.write_text('func main() int32:\n    return 0\n', encoding='utf-8')
            compiler = Compiler()
            compiler.project_root = root.resolve()

            self.assertIsNone(
                resolve_module_path(compiler, '../outside', main)
            )
            self.assertTrue(
                any('nombre de modulo' in error for error in compiler.semantic_errors)
            )

    def test_repeated_selective_alias_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'math.bg').write_text(
                'func doble(value: int32) int32:\n'
                '    return value + value\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import { doble as twice, doble as twice } from math\n'
                'func main() int32:\n'
                '    return twice(3)\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'alias importado se repite'):
                Compiler().compile(main, executable=False)

    def test_import_rejects_incompatible_system_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'linux_only.bg').write_text(
                "clause System 'linux'\n"
                'func value() int32:\n'
                '    return 1\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                "clause System 'windows'\n"
                'import linux_only\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'incompatible con el target'):
                Compiler().compile(main, executable=False)

    def test_import_rejects_incompatible_architecture_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'x86_only.bg').write_text(
                "clause Arch 'x86'\n"
                'func value() int32:\n'
                '    return 1\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                "clause Arch 'amd'\n"
                'import x86_only\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'incompatible con el target'):
                Compiler().compile(main, executable=False)

    def test_baremetal_accepts_explicit_sysv_amd64_abi(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'clause System "baremetal"\n'
                'clause Arch "amd"\n'
                'clause Boot "none"\n'
                'clause ABI "sysv_amd64"\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            compiler = Compiler()
            compiler.compile(main, executable=False)

        self.assertEqual('sysv_amd64', compiler.storage.abi)

    def test_baremetal_requires_an_explicit_abi(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'clause System "baremetal"\n'
                'clause Arch "amd"\n'
                'clause Boot "none"\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(
                CompilationError,
                'requiere una clausula ABI explicita',
            ):
                Compiler().compile(main, executable=False)

    def test_abi_clause_is_rejected_outside_baremetal(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'clause System "linux"\n'
                'clause Arch "amd"\n'
                'clause ABI "sysv_amd64"\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(
                CompilationError,
                'clausula ABI solo se permite con System "baremetal"',
            ):
                Compiler().compile(main, executable=False)

    def test_abi_clause_is_rejected_for_windows(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'clause System "windows"\n'
                'clause Arch "amd"\n'
                'clause ABI "sysv_amd64"\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(
                CompilationError,
                'clausula ABI solo se permite con System "baremetal"',
            ):
                Compiler().compile(main, executable=False)

    def test_sysv_amd64_abi_requires_amd64(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'clause System "baremetal"\n'
                'clause Arch "arm"\n'
                'clause Boot "none"\n'
                'clause ABI "sysv_amd64"\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(
                CompilationError,
                'sysv_amd64.*AMD64',
            ):
                Compiler().compile(main, executable=False)

    def test_unknown_baremetal_abi_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'clause System "baremetal"\n'
                'clause Arch "amd"\n'
                'clause Boot "none"\n'
                'clause ABI "custom_amd64"\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(
                CompilationError,
                'ABI.*(no esta soportada|valor invalido)',
            ):
                Compiler().compile(main, executable=False)

    def test_imported_abi_is_inherited_without_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'inherited_abi.bg').write_text(
                'public func value() int32:\n'
                '    return 1\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'clause System "baremetal"\n'
                'clause Arch "amd"\n'
                'clause Boot "none"\n'
                'clause ABI "sysv_amd64"\n'
                'import inherited_abi\n'
                'func main() int32:\n'
                '    return inherited_abi.value()\n',
                encoding='utf-8',
            )

            compiler = Compiler()
            compiler.compile(main, executable=False)

        self.assertEqual([], compiler.warnings)
        self.assertEqual('sysv_amd64', compiler.storage.abi)

    def test_import_rejects_incompatible_explicit_abi(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'custom_abi.bg').write_text(
                'clause ABI "custom_amd64"\n'
                'public func value() int32:\n'
                '    return 1\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'clause System "baremetal"\n'
                'clause Arch "amd"\n'
                'clause Boot "none"\n'
                'clause ABI "sysv_amd64"\n'
                'import custom_abi\n'
                'func main() int32:\n'
                '    return custom_abi.value()\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(
                CompilationError,
                'incompatible con la ABI del proyecto',
            ):
                Compiler().compile(main, executable=False)

    def test_baremetal_requires_an_explicit_boot_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'clause System "baremetal"\n'
                'clause Arch "amd"\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(
                CompilationError,
                'requiere una clausula Boot explicita',
            ):
                Compiler().compile(main, executable=False)

    def test_non_baremetal_rejects_boot_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'clause System "windows"\n'
                'clause Arch "amd"\n'
                'clause Boot "multiboot2"\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(
                CompilationError,
                'no admite un protocolo de arranque bare-metal',
            ):
                Compiler().compile(main, executable=False)

    def test_multiboot2_rejects_non_x86_architecture(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / '_main.bg'
            main.write_text(
                'clause System "baremetal"\n'
                'clause Arch "arm"\n'
                'clause Boot "multiboot2"\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(
                CompilationError,
                'Boot "multiboot2" para Arch .+aarch64',
            ):
                Compiler().compile(main, executable=False)

    def test_import_rejects_incompatible_boot_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'loader.bg').write_text(
                'clause System "baremetal"\n'
                'clause Arch "amd"\n'
                'clause Boot "none"\n'
                'func helper() void:\n'
                '    pass\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'clause System "baremetal"\n'
                'clause Arch "amd"\n'
                'clause Boot "multiboot2"\n'
                'import loader\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(
                CompilationError,
                'declara Boot .+incompatible con el target',
            ):
                Compiler().compile(main, executable=False)

    def test_import_inherits_entry_target_without_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'inherited.bg').write_text(
                'func value() int32:\n'
                '    return 1\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                "clause System 'windows'\n"
                "clause Arch 'amd'\n"
                'import inherited\n'
                'func main() int32:\n'
                '    return inherited.value()\n',
                encoding='utf-8',
            )

            compiler = Compiler()
            compiler.compile(main, executable=False)

        self.assertEqual([], compiler.warnings)
        self.assertEqual('windows', compiler.storage.system)
        self.assertEqual('amd', compiler.storage.architecture)

    def test_import_reports_cycles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'a.bg').write_text(
                'import b\n'
                'func doble(value: int32) int32:\n'
                '    return value + value\n',
                encoding='utf-8',
            )
            (root / 'b.bg').write_text(
                'import a\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import a\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'Ciclo de importacion'):
                Compiler().compile(main, executable=False)

    def test_import_reports_three_module_cycle_with_full_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'a.bg').write_text('import b\n', encoding='utf-8')
            (root / 'b.bg').write_text('import c\n', encoding='utf-8')
            (root / 'c.bg').write_text('import a\n', encoding='utf-8')
            main = root / '_main.bg'
            main.write_text(
                'import a\n'
                'func main() int32:\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaises(CompilationError) as context:
                Compiler().compile(main, executable=False)

        message = str(context.exception)
        self.assertIn('Ciclo de importacion detectado', message)
        self.assertIn('a.bg', message)
        self.assertIn('b.bg', message)
        self.assertIn('c.bg', message)

    def test_diamond_import_loads_shared_module_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'shared.bg').write_text(
                'func leaf() int32:\n'
                '    return 7\n',
                encoding='utf-8',
            )
            (root / 'left.bg').write_text(
                'import shared\n'
                'func from_left() int32:\n'
                '    return shared.leaf()\n',
                encoding='utf-8',
            )
            (root / 'right.bg').write_text(
                'import shared\n'
                'func from_right() int32:\n'
                '    return shared.leaf()\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                "clause Optimizations 'dev'\n"
                'import left\n'
                'import right\n'
                'func main() int32:\n'
                '    return left.from_left() + right.from_right()\n',
                encoding='utf-8',
            )

            compiler = Compiler()
            module_path = compiler.compile(main, executable=False)
            module = Path(module_path).read_text(encoding='utf-8')
            loaded_names = [
                Path(path).name for path in compiler.storage.loaded_modules
            ]

        self.assertEqual(4, len(loaded_names))
        self.assertEqual(4, len(set(loaded_names)))
        self.assertEqual(1, loaded_names.count('shared.bg'))
        self.assertEqual(1, len(re.findall(r'define i32 @"?__bg_[^"\s]*_leaf_[^"\s]*"?', module)))
        self.assertRegex(module, r'call i32 @"?__bg_[^"\s]*_from_left_[^"\s]*"?\(\)')
        self.assertRegex(module, r'call i32 @"?__bg_[^"\s]*_from_right_[^"\s]*"?\(\)')


    def test_import_does_not_resolve_module_from_bagron_root_modules(self):
        with tempfile.TemporaryDirectory() as fake_bagron_dir, tempfile.TemporaryDirectory() as project_dir:
            fake_bagron = Path(fake_bagron_dir)
            (fake_bagron / 'modules').mkdir()
            (fake_bagron / 'modules' / 'shared_tool.bg').write_text(
                'public func tool() int32:\n'
                '    return 99\n',
                encoding='utf-8',
            )

            root = Path(project_dir)
            main = root / '_main.bg'
            main.write_text(
                'import shared_tool\n'
                'func main() int32:\n'
                '    return shared_tool.tool()\n',
                encoding='utf-8',
            )

            from unittest.mock import patch
            with patch('core.globvars.BAGRON_ROOT', fake_bagron):
                with self.assertRaisesRegex(CompilationError, 'No se encontro el modulo'):
                    Compiler().compile(main, executable=False)

    def test_import_does_not_resolve_source_module_from_bagron_root_libs(self):
        with tempfile.TemporaryDirectory() as fake_bagron_dir, tempfile.TemporaryDirectory() as project_dir:
            fake_bagron = Path(fake_bagron_dir)
            (fake_bagron / 'libs').mkdir()
            (fake_bagron / 'libs' / 'global_lib.bg').write_text(
                'public func answer() int32:\n'
                '    return 42\n',
                encoding='utf-8',
            )

            root = Path(project_dir)
            main = root / '_main.bg'
            main.write_text(
                'import global_lib\n'
                'func main() int32:\n'
                '    return global_lib.answer()\n',
                encoding='utf-8',
            )

            from unittest.mock import patch
            with patch('core.globvars.BAGRON_ROOT', fake_bagron):
                with self.assertRaisesRegex(CompilationError, 'No se encontro el modulo'):
                    Compiler().compile(main, executable=False)

    def test_local_project_module_remains_available(self):
        with tempfile.TemporaryDirectory() as fake_bagron_dir, tempfile.TemporaryDirectory() as project_dir:
            fake_bagron = Path(fake_bagron_dir)

            root = Path(project_dir)
            (root / 'modules').mkdir()
            (root / 'modules' / 'io.bg').write_text(
                'public func ping() int32:\n'
                '    return 2\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import io\n'
                'func main() int32:\n'
                '    return io.ping()\n',
                encoding='utf-8',
            )

            from unittest.mock import patch
            with patch('core.globvars.BAGRON_ROOT', fake_bagron):
                compiler = Compiler()
                output = compiler.compile(main, executable=False)

            loaded_io = [p for p in compiler.storage.loaded_modules if 'io.bg' in p][0]
            self.assertEqual((root / 'modules' / 'io.bg').resolve(), Path(loaded_io).resolve())

if __name__ == '__main__':
    unittest.main()


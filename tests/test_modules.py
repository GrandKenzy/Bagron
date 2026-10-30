from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler
from core.frontend.tools.imports import resolve_module_path


class ModuleTests(unittest.TestCase):
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
                'import math\n'
                'func main() int32:\n'
                '    return doble(3)\n',
                encoding='utf-8',
            )

            compiler = Compiler()
            output = compiler.compile(main, executable=False)
            module = Path(output).read_text(encoding='utf-8')

        self.assertIn('define i32 @"doble"', module)
        self.assertIn('call i32 @"doble"(i32 3)', module)
        self.assertEqual(2, len(compiler.storage.loaded_modules))

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
                'import math as m\n'
                'func main() int32:\n'
                '    return m.doble(3)\n',
                encoding='utf-8',
            )

            module_path = Compiler().compile(main, executable=False)
            module = Path(module_path).read_text(encoding='utf-8')

        self.assertIn('call i32 @"doble"(i32 3)', module)

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
                'import { doble as twice } from math\n'
                'func main() int32:\n'
                '    return twice(3)\n',
                encoding='utf-8',
            )

            module_path = Compiler().compile(main, executable=False)
            module = Path(module_path).read_text(encoding='utf-8')

        self.assertIn('call i32 @"doble"(i32 3)', module)

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
                'import { doble as n, triple as t } from math\n'
                'func main() int32:\n'
                '    return n(2) + t(2)\n',
                encoding='utf-8',
            )

            module_path = Compiler().compile(main, executable=False)
            module = Path(module_path).read_text(encoding='utf-8')

        self.assertIn('call i32 @"doble"(i32 2)', module)
        self.assertIn('call i32 @"triple"(i32 2)', module)

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
                'import arrays as a\n'
                'func main() int32:\n'
                '    values: int32[3] = {1, 2, 3}\n'
                '    return a.total(values)\n',
                encoding='utf-8',
            )

            module_path = Compiler().compile(main, executable=False)
            module = Path(module_path).read_text(encoding='utf-8')

        self.assertIn('define i32 @"total"', module)
        self.assertRegex(module, r'call i32 @"total"\([^)]*i64 3, i64 4\)')

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

    def test_private_global_is_not_accepted_by_global_declaration(self):
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
                '    global secret\n'
                '    return secret\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'solo puede referirse'):
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

    def test_target_agnostic_import_emits_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'agnostic.bg').write_text(
                'func value() int32:\n'
                '    return 1\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                "clause System 'windows'\n"
                "clause Arch 'amd'\n"
                'import agnostic\n'
                'func main() int32:\n'
                '    return value()\n',
                encoding='utf-8',
            )

            compiler = Compiler()
            compiler.compile(main, executable=False)

        self.assertTrue(any('agnostico' in warning for warning in compiler.warnings))

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
                '    return leaf()\n',
                encoding='utf-8',
            )
            (root / 'right.bg').write_text(
                'import shared\n'
                'func from_right() int32:\n'
                '    return leaf()\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import left\n'
                'import right\n'
                'func main() int32:\n'
                '    return from_left() + from_right()\n',
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
        self.assertEqual(1, module.count('define i32 @"leaf"'))
        self.assertIn('call i32 @"from_left"()', module)
        self.assertIn('call i32 @"from_right"()', module)

if __name__ == '__main__':
    unittest.main()

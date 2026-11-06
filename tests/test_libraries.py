from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from core.compiler import Compiler
from core.frontend.aot import AotInMemoryParser
from core.library import (
    HEADER,
    LibraryError,
    inspect_library,
    pack_library,
    unpack_library,
    verify_library,
)


class LibraryTests(unittest.TestCase):
    def _source(self, root: Path) -> Path:
        source = root / 'source'
        source.mkdir()
        (source / 'string.bg').write_text(
            'public func convert() int32:\n'
            '    return 42\n'
            'public Answer: const int32 = 42\n'
            'private func hidden() int32:\n'
            '    return 7\n',
            encoding='utf-8',
        )
        return source

    def test_package_verify_inspect_and_unpack(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root)
            package_path = root / 'libs' / 'My.lib'
            package_path.parent.mkdir()

            pack_library(source, package_path, name='My', version='1.0.0')
            package = verify_library(package_path)
            info = inspect_library(package_path)
            destination = root / 'unpacked'
            unpack_library(package_path, destination)

            self.assertEqual('My', package.name)
            self.assertEqual('bagron-library', info['manifest']['format'])
            self.assertEqual(1, info['library_version'])
            exports = {item['name'] for item in info['exports']}
            self.assertEqual({'convert', 'Answer'}, exports)
            self.assertTrue((destination / 'source' / 'string.bg').is_file())
            self.assertTrue((destination / 'symbols.json').is_file())
            self.assertTrue((destination / 'ir' / 'modules.json').is_file())

    def test_library_import_compiles_through_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root)
            package_path = root / 'libs' / 'My.lib'
            package_path.parent.mkdir()
            pack_library(source, package_path, name='My', version='1.0.0')
            main = root / 'main.bg'
            main.write_text(
                'library "My.lib" as Lib\n'
                'func main() int32:\n'
                '    return Lib.convert()\n',
                encoding='utf-8',
            )

            compiler = Compiler()
            artifact = compiler.compile(main, executable=False)
            self.assertTrue(Path(artifact).is_file())

    def test_libs_directory_is_the_canonical_library_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root)
            (root / 'libs').mkdir()
            package_path = root / 'libs' / 'My.lib'
            pack_library(source, package_path, name='My', version='1.0.0')
            main = root / 'main.bg'
            main.write_text(
                'library "My.lib" as Lib\n'
                'func main() int32:\n'
                '    return Lib.convert()\n',
                encoding='utf-8',
            )

            artifact = Compiler().compile(main, executable=False)
            self.assertTrue(Path(artifact).is_file())

    def test_conditional_library_directive_selects_the_target_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root)
            (root / 'libs').mkdir()
            package_path = root / 'libs' / 'My.lib'
            pack_library(source, package_path, name='My', version='1.0.0')
            main = root / 'main.bg'
            main.write_text(
                'clause System \'windows\'\n'
                '#if OS, "windows"\n'
                'library "My.lib" as Lib\n'
                '#elif OS, "linux"\n'
                'library "missing.lib" as Missing\n'
                '#end\n'
                'func main() int32:\n'
                '    return Lib.convert()\n',
                encoding='utf-8',
            )

            artifact = Compiler().compile(main, executable=False)
            self.assertTrue(Path(artifact).is_file())

    def test_lib1_metadata_selects_conditional_main_clauses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (source / 'main.bg').write_text(
                '#if OS, "windows"\n'
                'clause System "windows"\n'
                'clause Arch "amd"\n'
                '#elif OS, "linux"\n'
                'clause System "linux"\n'
                'clause Arch "amd"\n'
                '#else\n'
                'clause System "auto"\n'
                'clause Arch "auto"\n'
                '#end\n',
                encoding='utf-8',
            )
            (source / 'value.bg').write_text(
                'public func value() int32:\n'
                '    return 42\n',
                encoding='utf-8',
            )

            package_path = root / 'Conditional.lib'
            pack_library(source, package_path, name='Conditional', version='1.0.0')

            self.assertEqual(
                'windows',
                verify_library(package_path).manifest['targets']['System'],
            )

    def test_lib1_validation_uses_main_target_and_library_directives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dependency_source = root / 'dependency'
            dependency_source.mkdir()
            (dependency_source / 'value.bg').write_text(
                'public func value() int32:\n'
                '    return 42\n',
                encoding='utf-8',
            )

            source = root / 'source'
            (source / 'modules').mkdir(parents=True)
            (source / 'libs').mkdir()
            (source / 'main.bg').write_text(
                'clause System "windows"\n'
                'clause Arch "amd"\n'
                'library "Dependency.lib" as Dependency\n',
                encoding='utf-8',
            )
            (source / 'modules' / 'consumer.bg').write_text(
                'public func answer() int32:\n'
                '    return Dependency.value()\n',
                encoding='utf-8',
            )
            pack_library(
                dependency_source,
                source / 'libs' / 'Dependency.lib',
                name='Dependency',
                version='1.0.0',
            )

            package_path = root / 'DependencyConsumer.lib'
            pack_library(source, package_path, name='Consumer', version='1.0.0')
            self.assertEqual('windows', verify_library(package_path).manifest['targets']['System'])

    def test_package2_contains_native_object_without_source_or_ir(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (source / 'math.bg').write_text(
                'public func convert() int32:\n'
                '    return 42\n',
                encoding='utf-8',
            )
            package_path = root / 'libs' / 'Math.lib'
            package_path.parent.mkdir()

            from core.library import pack_compiled_library

            pack_compiled_library(source, package_path, name='Math', version='1.0.0')
            package = verify_library(package_path)
            destination = root / 'unpacked'
            unpack_library(package_path, destination)

            self.assertEqual('compiled', package.kind)
            self.assertEqual(2, package.library_version)
            self.assertEqual({}, package.ir)
            self.assertTrue(package.artifacts['object'].startswith('objects/'))
            self.assertTrue((destination / package.artifacts['object']).is_file())
            self.assertFalse((destination / 'source').exists())

            main = root / 'main.bg'
            main.write_text(
                'library "Math.lib" as Lib\n'
                'func main() int32:\n'
                '    return Lib.convert()\n',
                encoding='utf-8',
            )
            artifact = Compiler().compile(main, executable=False)
            self.assertTrue(Path(artifact).is_file())

    def test_tampered_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root)
            package_path = root / 'My.lib'
            pack_library(source, package_path)
            data = bytearray(package_path.read_bytes())
            # The manifest digest starts after the fixed header fields.
            data[32] ^= 0xFF
            package_path.write_bytes(data)
            with self.assertRaisesRegex(LibraryError, 'SHA'):
                verify_library(package_path)

    def test_tampered_each_integrity_section_is_rejected(self):
        for offset in (32, 64, 96, 128, 160):
            with self.subTest(offset=offset), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                package_path = root / 'My.lib'
                pack_library(self._source(root), package_path)
                data = bytearray(package_path.read_bytes())
                data[offset] ^= 0xFF
                package_path.write_bytes(data)
                with self.assertRaises(LibraryError):
                    verify_library(package_path)

    def test_library_consumption_uses_serialized_ir_not_package_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_path = root / 'My.lib'
            package_path = root / 'libs' / 'My.lib'
            package_path.parent.mkdir()
            pack_library(self._source(root), package_path)
            main = root / 'main.bg'
            main.write_text(
                'library "My.lib" as Lib\n'
                'func main() int32:\n'
                '    return Lib.convert()\n',
                encoding='utf-8',
            )
            original_parse = AotInMemoryParser.parse

            def parse_without_package_source(parser, content, *, session, name):
                if '/source/' in str(name).replace('\\', '/'):
                    raise AssertionError('se volvio a analizar source/ de lib1')
                return original_parse(parser, content, session=session, name=name)

            with patch.object(AotInMemoryParser, 'parse', parse_without_package_source):
                artifact = Compiler().compile(main, executable=False)
            self.assertTrue(Path(artifact).is_file())

    def test_lib1_preserves_internal_imports_and_assembler_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            modules = source / 'modules'
            modules.mkdir(parents=True)
            (modules / 'base.bg').write_text(
                'public func base_value() int32:\n'
                '    return 40\n',
                encoding='utf-8',
            )
            (modules / 'native.bg').write_text(
                'import base\n'
                '@assembler\n'
                'public func answer() int32:\n'
                '    #assembler "intel"\n'
                '        mov eax, 2\n'
                '    #end\n'
                '    return asm\n'
                '@unsafe\n'
                'public func total() int32:\n'
                '    return base.base_value() + answer()\n',
                encoding='utf-8',
            )
            package_path = root / 'libs' / 'Native.lib'
            package_path.parent.mkdir()
            pack_library(source, package_path, name='Native', version='1.0.0')

            main = root / 'main.bg'
            main.write_text(
                'library "Native.lib" as Native\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    return Native.total()\n',
                encoding='utf-8',
            )

            artifact = Compiler().compile(main, executable=False)
            self.assertTrue(Path(artifact).is_file())

    def test_header_has_binary_magic_and_fixed_zip_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_path = root / 'My.lib'
            pack_library(self._source(root), package_path)
            data = package_path.read_bytes()
            self.assertEqual(b'BGLIB1\0\0', data[:8])
            self.assertEqual(HEADER.size, int.from_bytes(data[14:16], 'little'))
            self.assertEqual(HEADER.size, int.from_bytes(data[16:24], 'little'))

    def test_package_rejects_path_escape_entry(self):
        from core.library import _safe_member

        with self.assertRaisesRegex(LibraryError, 'escapa'):
            _safe_member('../outside.bg')
        with self.assertRaisesRegex(LibraryError, 'escapa'):
            _safe_member('/absolute/path')


if __name__ == '__main__':
    unittest.main()

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from core.compiler import CompilationError, Compiler
from core.compiler.platforms import detect_host_system
from core.frontend.aot import AotInMemoryParser
from core.lockfile import update_lockfile
from core.lockfile import LockfileError, validate_lock_graph
from core.library import (
    HEADER,
    LibraryError,
    compute_library_signature,
    extract_library_directives,
    extract_library,
    inspect_library,
    pack_library,
    sign_library_metadata,
    unpack_library,
    verify_library,
    verify_library_signature,
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

    def _rewrite_zip_payload(self, package_path: Path, mutator) -> None:
        """Rewrite a test package while preserving its signed header fields."""
        raw = package_path.read_bytes()
        fields = list(HEADER.unpack(raw[:HEADER.size]))
        source = io.BytesIO(raw[HEADER.size:])
        output = io.BytesIO()
        with zipfile.ZipFile(source, 'r') as archive, zipfile.ZipFile(output, 'w') as rebuilt:
            entries = {
                info.filename: archive.read(info)
                for info in archive.infolist()
                if not info.is_dir()
            }
            entries = mutator(entries)
            for name, data in entries.items():
                info = zipfile.ZipInfo(name)
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                rebuilt.writestr(info, data)
        zip_bytes = output.getvalue()
        manifest_bytes = entries['manifest.json']
        fields[7] = len(zip_bytes)
        fields[8] = hashlib.sha256(manifest_bytes).digest()
        package_path.write_bytes(HEADER.pack(*fields) + zip_bytes)

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
            self.assertEqual('lib1', info['format'])
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

    def test_library_modules_can_be_nested_without_namespace_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            (source / 'modules' / 'ui' / 'rendering').mkdir(parents=True)
            (source / 'modules' / 'ui' / 'widgets.bg').write_text(
                'public func value() int32:\n'
                '    return 7\n',
                encoding='utf-8',
            )
            (source / 'modules' / 'ui' / 'rendering' / 'draw.bg').write_text(
                'import widgets\n'
                'public func draw() int32:\n'
                '    return widgets.value()\n',
                encoding='utf-8',
            )
            package_path = root / 'libs' / 'Nested.lib'
            package_path.parent.mkdir()
            pack_library(source, package_path, name='Nested', version='1.0.0')
            main = root / 'main.bg'
            main.write_text(
                'library "Nested.lib" as Lib\n'
                'func main() int32:\n'
                '    return Lib.draw()\n',
                encoding='utf-8',
            )

            artifact = Compiler().compile(main, executable=False)
            self.assertTrue(Path(artifact).is_file())

    def test_library_namespace_can_qualify_nominal_types(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (source / 'main.bg').write_text(
                'public struct FileInfo:\n'
                '    code: int32\n'
                'public func make_info(value: int32) FileInfo:\n'
                '    info: FileInfo\n'
                '    info.code = value\n'
                '    return info\n',
                encoding='utf-8',
            )
            package_path = root / 'libs' / 'Metadata.lib'
            package_path.parent.mkdir()
            pack_library(source, package_path, name='Metadata', version='1.0.0')
            main = root / 'main.bg'
            main.write_text(
                'library "Metadata.lib" as Meta\n'
                'func main() int32:\n'
                '    info: Meta.FileInfo = Meta.make_info(42)\n'
                '    return info.code\n',
                encoding='utf-8',
            )

            artifact = Compiler().compile(main, executable=False)
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

    def test_bare_library_name_resolves_from_bagron_libs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bagron_root = root / 'bagron'
            (bagron_root / 'libs').mkdir(parents=True)
            dependency_source = root / 'dependency-source'
            dependency_source.mkdir()
            (dependency_source / 'value.bg').write_text(
                'public func convert() int32:\n'
                '    return 42\n',
                encoding='utf-8',
            )
            pack_library(
                dependency_source,
                bagron_root / 'libs' / 'Global.lib',
                name='Global',
                version='1.0.0',
            )

            project = root / 'project'
            project.mkdir()
            main = project / 'main.bg'
            main.write_text(
                'library Global as Lib\n'
                'func main() int32:\n'
                '    return Lib.convert()\n',
                encoding='utf-8',
            )

            with patch('core.globvars.BAGRON_ROOT', bagron_root):
                artifact = Compiler().compile(main, executable=False)
            self.assertTrue(Path(artifact).is_file())

    def test_library_directive_preserves_global_lookup_scope(self):
        source = Path('project') / 'main.bg'
        _, requests, errors = extract_library_directives(
            ['library gnulibrary as gnu\n'],
            source,
            allow=True,
        )

        self.assertEqual([], errors)
        self.assertEqual(1, len(requests))
        self.assertEqual('gnulibrary', requests[0].path)
        self.assertTrue(requests[0].global_name)

    def test_lib1_validation_preserves_global_library_directive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bagron_root = root / 'bagron'
            (bagron_root / 'libs').mkdir(parents=True)
            dependency_source = root / 'dependency-source'
            dependency_source.mkdir()
            (dependency_source / 'value.bg').write_text(
                'public func value() int32:\n'
                '    return 42\n',
                encoding='utf-8',
            )
            pack_library(
                dependency_source,
                bagron_root / 'libs' / 'Dependency.lib',
                name='Dependency',
                version='1.0.0',
            )

            source = root / 'source'
            (source / 'modules').mkdir(parents=True)
            (source / 'main.bg').write_text(
                'clause System "windows"\n'
                'clause Arch "amd"\n'
                'library Dependency as Dependency\n',
                encoding='utf-8',
            )
            (source / 'modules' / 'consumer.bg').write_text(
                'public func answer() int32:\n'
                '    return Dependency.value()\n',
                encoding='utf-8',
            )

            package_path = root / 'Consumer.lib'
            with patch('core.globvars.BAGRON_ROOT', bagron_root):
                pack_library(
                    source,
                    package_path,
                    name='Consumer',
                    version='1.0.0',
                )

            self.assertEqual('Consumer', verify_library(package_path).name)

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
                detect_host_system(),
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

    def test_package2_accepts_nested_modules_with_flat_import_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            (source / 'modules' / 'ui' / 'rendering').mkdir(parents=True)
            (source / 'modules' / 'ui' / 'widgets.bg').write_text(
                'public func value() int32:\n'
                '    return 7\n',
                encoding='utf-8',
            )
            (source / 'modules' / 'ui' / 'rendering' / 'draw.bg').write_text(
                'import widgets\n'
                'public func draw() int32:\n'
                '    return widgets.value()\n',
                encoding='utf-8',
            )
            package_path = root / 'libs' / 'Nested.lib'
            package_path.parent.mkdir()

            from core.library import pack_compiled_library

            pack_compiled_library(source, package_path, name='Nested', version='1.0.0')
            main = root / 'main.bg'
            main.write_text(
                'library "Nested.lib" as Lib\n'
                'func main() int32:\n'
                '    return Lib.draw()\n',
                encoding='utf-8',
            )

            artifact = Compiler().compile(main, executable=False)
            self.assertTrue(Path(artifact).is_file())

    def test_lib2_rejects_native_object_missing_from_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (source / 'math.bg').write_text(
                'public func convert() int32:\n'
                '    return 42\n',
                encoding='utf-8',
            )
            package_path = root / 'Math.lib'
            from core.library import pack_compiled_library
            pack_compiled_library(source, package_path, name='Math', version='1.0.0')

            def remove_object(entries):
                manifest = json.loads(entries['manifest.json'])
                object_name = json.loads(entries['artifacts.json'])['object']
                manifest['files'] = [
                    item for item in manifest['files']
                    if item['path'] != object_name
                ]
                entries['manifest.json'] = json.dumps(
                    manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')
                ).encode('utf-8')
                return entries

            self._rewrite_zip_payload(package_path, remove_object)
            with self.assertRaisesRegex(LibraryError, 'no coincide exactamente|no declarado'):
                verify_library(package_path)

    def test_package_rejects_unlisted_zip_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_path = root / 'My.lib'
            source = self._source(root)
            pack_library(source, package_path)

            def add_extra(entries):
                entries['unexpected.bin'] = b'not declared'
                return entries

            self._rewrite_zip_payload(package_path, add_extra)
            with self.assertRaisesRegex(LibraryError, 'no coincide exactamente'):
                verify_library(package_path)

    def test_package_rejects_nontextual_manifest_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_path = root / 'My.lib'
            pack_library(self._source(root), package_path)

            def replace_path_with_number(entries):
                manifest = json.loads(entries['manifest.json'])
                manifest['files'][0]['path'] = 7
                entries['manifest.json'] = json.dumps(
                    manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')
                ).encode('utf-8')
                return entries

            self._rewrite_zip_payload(package_path, replace_path_with_number)
            with self.assertRaisesRegex(LibraryError, 'ruta textual'):
                verify_library(package_path)

    def test_lock_graph_rejects_missing_transitive_package(self):
        from types import SimpleNamespace

        package = SimpleNamespace(
            name='root',
            manifest={'version': '1.0.0', 'dependencies': ['child']},
            archive_sha256='a' * 64,
            library_version=1,
        )
        lock_data = {
            'format': 'bagron-lock@1',
            'target': {'system': 'auto', 'architecture': 'auto'},
            'packages': {
                'root': {
                    'version': '1.0.0',
                    'source': 'local:root.lib',
                    'sha256': 'a' * 64,
                    'package_format': 'lib1',
                    'dependencies': ['child'],
                },
            },
        }
        with self.assertRaisesRegex(LockfileError, 'transitiva'):
            validate_lock_graph(lock_data, [package])

    def test_extraction_rebuilds_a_tampered_cache_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_path = root / 'My.lib'
            pack_library(self._source(root), package_path)
            package, extracted = extract_library(package_path, root / 'cache')
            original = (extracted / 'source' / 'string.bg').read_bytes()
            (extracted / 'source' / 'string.bg').write_bytes(b'tampered')
            package_again, extracted_again = extract_library(package_path, root / 'cache')
            self.assertEqual(package.archive_sha256, package_again.archive_sha256)
            self.assertEqual(original, (extracted_again / 'source' / 'string.bg').read_bytes())

    def test_extraction_does_not_reuse_a_symlink_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_path = root / 'My.lib'
            source = self._source(root)
            expected = (source / 'string.bg').read_bytes()
            pack_library(source, package_path)
            _, extracted = extract_library(package_path, root / 'cache')
            marker = extracted / '.complete'
            marker.unlink()
            try:
                marker.symlink_to(root / 'source' / 'string.bg')
            except (OSError, NotImplementedError) as error:
                self.skipTest(f'symlinks unavailable: {error}')

            _, rebuilt = extract_library(package_path, root / 'cache')
            self.assertFalse((rebuilt / '.complete').is_symlink())
            self.assertEqual(expected, (rebuilt / 'source' / 'string.bg').read_bytes())

    def test_unpack_rejects_symlink_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_path = root / 'My.lib'
            pack_library(self._source(root), package_path)
            outside = root / 'outside'
            outside.mkdir()
            destination = root / 'unpacked'
            try:
                destination.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f'symlinks unavailable: {error}')

            with self.assertRaisesRegex(LibraryError, 'enlace simbólico'):
                unpack_library(package_path, destination)
            self.assertFalse((outside / 'source').exists())

    def test_compilation_honors_bagron_lock_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root)
            package_path = root / 'libs' / 'My.lib'
            package_path.parent.mkdir()
            pack_library(source, package_path, name='My', version='1.0.0')
            package_bytes = package_path.read_bytes()
            update_lockfile(
                root / 'bagron.lock',
                name='My',
                version='1.0.0',
                source='local:libs/My.lib',
                package_format='lib1',
                data=package_bytes,
            )
            main = root / 'main.bg'
            main.write_text(
                'library "My.lib" as Lib\n'
                'func main() int32:\n'
                '    return Lib.convert()\n',
                encoding='utf-8',
            )
            self.assertTrue(Path(Compiler().compile(main, executable=False)).is_file())

            lock = json.loads((root / 'bagron.lock').read_text(encoding='utf-8'))
            lock['packages']['My']['sha256'] = '0' * 64
            (root / 'bagron.lock').write_text(
                json.dumps(lock), encoding='utf-8'
            )
            with self.assertRaisesRegex(CompilationError, 'digest bloqueado'):
                Compiler().compile(main, executable=False)

    def test_shared_library_is_extracted_once_per_compilation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_path = root / 'libs' / 'My.lib'
            package_path.parent.mkdir()
            pack_library(self._source(root), package_path, name='My', version='1.0.0')
            main = root / 'main.bg'
            main.write_text(
                'library "My.lib" as First\n'
                'library "My.lib" as Second\n'
                'func main() int32:\n'
                '    return First.convert()\n',
                encoding='utf-8',
            )
            with patch('core.compiler.extract_library', wraps=extract_library) as loader:
                Compiler().compile(main, executable=False)
            self.assertEqual(1, loader.call_count)

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


    def test_library_dependencies_in_main_loaded_and_not_polluting_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_source = root / 'base'
            (base_source / 'modules').mkdir(parents=True)
            (base_source / 'modules' / 'util.bg').write_text(
                'public func base_val() int32:\n'
                '    return 42\n',
                encoding='utf-8',
            )
            base_lib = root / 'Base.lib'
            pack_library(base_source, base_lib, name='Base', version='1.0.0')

            consumer_source = root / 'consumer'
            (consumer_source / 'libs').mkdir(parents=True)
            (consumer_source / 'libs' / 'Base.lib').write_bytes(base_lib.read_bytes())
            (consumer_source / 'main.bg').write_text(
                'library "Base.lib" as Base\n',
                encoding='utf-8',
            )
            (consumer_source / 'modules').mkdir(parents=True)
            (consumer_source / 'modules' / 'calc.bg').write_text(
                'public func calc() int32:\n'
                '    return Base.base_val() + 1\n',
                encoding='utf-8',
            )
            consumer_lib = root / 'Consumer.lib'
            pack_library(consumer_source, consumer_lib, name='Consumer', version='1.0.0')

            info = inspect_library(consumer_lib)
            export_names = {item['name'] for item in info.get('exports', ())}
            self.assertIn('calc', export_names)
            self.assertNotIn('base_val', export_names)

            app = root / 'app'
            (app / 'libs').mkdir(parents=True)
            (app / 'libs' / 'Consumer.lib').write_bytes(consumer_lib.read_bytes())
            app_main = app / 'main.bg'
            app_main.write_text(
                'library "Consumer.lib" as Consumer\n'
                'func main() int32:\n'
                '    return Consumer.calc()\n',
                encoding='utf-8',
            )
            artifact = Compiler().compile(app_main, executable=False)
            self.assertTrue(Path(artifact).is_file())



    def test_compute_sign_and_verify_library_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root)
            meta = source / 'meta.toml'
            meta.write_text(
                '[package]\n'
                'name = "MyLib"\n'
                'version = "1.0.0"\n\n'
                '[author]\n'
                'name = "Discentra Community"\n'
                'signature = ""\n',
                encoding='utf-8',
            )
            sig = sign_library_metadata(source)
            self.assertTrue(sig.startswith('sha256:'))
            valid, msg = verify_library_signature(source)
            self.assertTrue(valid)
            self.assertEqual(sig, msg)

    def test_signature_verification_detects_tampered_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root)
            meta = source / 'meta.toml'
            meta.write_text(
                '[package]\n'
                'name = "MyLib"\n'
                'version = "1.0.0"\n\n'
                '[author]\n'
                'name = "Discentra Community"\n'
                'signature = ""\n',
                encoding='utf-8',
            )
            sign_library_metadata(source)
            (source / 'string.bg').write_text('// tampered', encoding='utf-8')
            valid, msg = verify_library_signature(source)
            self.assertFalse(valid)
            self.assertIn('Firma inválida', msg)

    def test_pack_library_auto_signs_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root)
            meta = source / 'meta.toml'
            meta.write_text(
                '[package]\n'
                'name = "AutoSigned"\n'
                'version = "1.2.3"\n\n'
                '[author]\n'
                'name = "Discentra Community"\n'
                'signature = ""\n',
                encoding='utf-8',
            )
            out_lib = root / 'AutoSigned.lib'
            pack_library(source, out_lib)
            updated_meta = meta.read_text(encoding='utf-8')
            self.assertIn('signature = "sha256:', updated_meta)
            valid, _ = verify_library_signature(source)
            self.assertTrue(valid)


    def test_import_from_library_alias_shadows_project_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bagron_root = root / 'bagron'
            (bagron_root / 'libs').mkdir(parents=True)
            lib_source = root / 'mylib_src'
            lib_source.mkdir()
            (lib_source / 'main.bg').write_text(
                'clause Privacy "public"\n'
                'public struct Item:\n'
                '    code: int32\n'
                'public func make_item(c: int32) Item:\n'
                '    item: Item\n'
                '    item.code = c\n'
                '    return item\n',
                encoding='utf-8',
            )
            pack_library(lib_source, bagron_root / 'libs' / 'mylib.lib', name='mylib', version='1.0.0')

            project = root / 'project'
            project.mkdir()
            (project / 'mylib').mkdir()
            (project / 'mylib' / 'main.bg').write_text(
                'clause System "windows"\nlibrary windows as Platform\n',
                encoding='utf-8',
            )

            main = project / 'main.bg'
            main.write_text(
                'library mylib as MyLib\n'
                'import { Item } from MyLib\n'
                'func main() int32:\n'
                '    it: Item = MyLib.make_item(42)\n'
                '    if it.code != 42:\n'
                '        return 1\n'
                '    return 0\n',
                encoding='utf-8',
            )
            with patch('core.globvars.BAGRON_ROOT', bagron_root):
                artifact = Compiler().compile(main, executable=False)
            self.assertTrue(Path(artifact).is_file())

    def test_library_types_require_explicit_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bagron_root = root / 'bagron'
            (bagron_root / 'libs').mkdir(parents=True)
            lib_source = root / 'mylib_src'
            lib_source.mkdir()
            (lib_source / 'main.bg').write_text(
                'clause Privacy "public"\n'
                'public struct Item:\n'
                '    code: int32\n',
                encoding='utf-8',
            )
            pack_library(lib_source, bagron_root / 'libs' / 'mylib.lib', name='mylib', version='1.0.0')

            project = root / 'project'
            project.mkdir()
            main = project / 'main.bg'
            main.write_text(
                'library mylib as MyLib\n'
                'func main() int32:\n'
                '    it: Item\n'
                '    return 0\n',
                encoding='utf-8',
            )
            with patch('core.globvars.BAGRON_ROOT', bagron_root):
                with self.assertRaises(CompilationError):
                    Compiler().compile(main, executable=False)


    def test_pack_library_rejects_duplicate_symbol_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            modules = source / 'modules'
            modules.mkdir(parents=True)
            (source / 'main.bg').write_text('clause Privacy "public"\n', encoding='utf-8')
            (modules / 'mod_a.bg').write_text(
                'public func compute() int32:\n'
                '    return 1\n',
                encoding='utf-8',
            )
            (modules / 'mod_b.bg').write_text(
                'public func compute() int32:\n'
                '    return 2\n',
                encoding='utf-8',
            )
            out_lib = root / 'Dup.lib'
            with self.assertRaises(LibraryError) as ctx:
                pack_library(source, out_lib, name='Dup', version='1.0.0')
            self.assertIn('comparten espacio de nombres, usa un prefijo', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()

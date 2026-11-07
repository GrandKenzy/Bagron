"""Bagron lib1 packages.

The lib1 container is deliberately small and deterministic: a fixed binary
header is followed by a ZIP payload containing the manifest, public symbol
table, frontend snapshot, source tree, and native dependency directories.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import tempfile
import tomllib
from typing import Iterable, Sequence
import zipfile

from core.compiler.mangling import MANGLE_VERSION, package_identity
from core.frontend.objects import (
    AggregateSymbol,
    EnumSymbol,
    FunctionSymbol,
    OpaqueSymbol,
    Variable,
)


MAGIC = b'BGLIB1\0\0'
FORMAT_MAJOR = 1
FORMAT_MINOR = 0
KIND_LIB1 = 1
KIND_LIB2 = 2
HEADER = struct.Struct('<8sHHBBHQQ32s32s32s32s32s')


class LibraryError(RuntimeError):
    """Raised when a lib1 package is invalid or cannot be prepared."""


@dataclass(frozen=True)
class LibraryRequest:
    path: str
    alias: str
    source: Path
    global_name: bool = False


def _format_library_directive(request: LibraryRequest) -> str:
    """Render a library request while preserving its lookup scope."""
    if request.global_name:
        return f'library {request.path} as {request.alias}\n'
    return f'library "{request.path}" as {request.alias}\n'


@dataclass(frozen=True)
class LibraryPackage:
    path: Path
    header: dict[str, object]
    manifest: dict[str, object]
    symbols: dict[str, object]
    ir: dict[str, object]
    artifacts: dict[str, object] = field(default_factory=dict)

    @property
    def kind(self) -> str:
        return str(self.header.get('kind', 'source'))

    @property
    def library_version(self) -> int:
        value = self.header.get('library_version')
        if value is not None:
            return int(value)
        return 2 if self.header.get('kind') == 'lib2' else 1

    @property
    def package_id(self) -> str:
        return str(self.manifest['package_id'])

    @property
    def name(self) -> str:
        return str(self.manifest['name'])

    @property
    def modules(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.manifest.get('modules', ()))

    @property
    def targets(self) -> dict[str, str]:
        values = self.manifest.get('targets', self.manifest.get('target', {}))
        return dict(values) if isinstance(values, dict) else {}


def _sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _sha_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')


def _stable_content_hash(files: Iterable[tuple[str, bytes]]) -> bytes:
    digest = hashlib.sha256()
    for name, data in sorted(files, key=lambda item: item[0]):
        digest.update(name.encode('utf-8'))
        digest.update(b'\0')
        digest.update(data)
    return digest.digest()


def _safe_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise LibraryError(f'La ruta del paquete escapa de su raiz: {name!r}')
    if not name or name.endswith('/'):
        return path
    return path


def _read_header(data: bytes) -> tuple[dict[str, object], int]:
    if len(data) < HEADER.size:
        raise LibraryError('El archivo no contiene un header lib1/lib2 completo')
    (
        magic,
        major,
        minor,
        kind,
        flags,
        header_size,
        zip_offset,
        zip_size,
        manifest_sha,
        symbols_sha,
        ir_sha,
        source_sha,
        package_sha,
    ) = HEADER.unpack_from(data)
    if magic != MAGIC:
        raise LibraryError('El archivo no tiene el magic de una libreria Bagron')
    if major != FORMAT_MAJOR:
        raise LibraryError(
            f'Version de libreria no compatible: {major}.{minor}; '
            f'se esperaba {FORMAT_MAJOR}.x'
        )
    if kind not in {KIND_LIB1, KIND_LIB2}:
        raise LibraryError(f'Tipo de libreria Bagron no soportado: {kind}')
    if header_size != HEADER.size or zip_offset != header_size:
        raise LibraryError('El header de libreria tiene offsets invalidos')
    if zip_size != len(data) - zip_offset:
        raise LibraryError('El tamano ZIP del header no coincide')
    return ({
        'magic': magic.decode('ascii', errors='replace'),
        'version': [major, minor],
        'kind': 'source' if kind == KIND_LIB1 else 'compiled',
        'library_version': kind,
        'flags': flags,
        'header_size': header_size,
        'zip_offset': zip_offset,
        'zip_size': zip_size,
        'manifest_sha': manifest_sha.hex(),
        'symbols_sha': symbols_sha.hex(),
        'ir_sha': ir_sha.hex(),
        'source_sha': source_sha.hex(),
        'package_sha': package_sha.hex(),
    }, zip_offset)


def _load_zip(path: Path) -> tuple[LibraryPackage, zipfile.ZipFile, bytes]:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise LibraryError(f'No se pudo leer la libreria {path}: {error}') from error
    header, offset = _read_header(data)
    payload = data[offset:]
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload), 'r')
        names = {_safe_member(name).as_posix() for name in archive.namelist()}
        required_names = ['manifest.json', 'symbols.json']
        if header['library_version'] == 1:
            required_names.append('ir/modules.json')
        else:
            required_names.append('artifacts.json')
        for required in required_names:
            if required not in names:
                raise LibraryError(f'Falta la seccion requerida {required!r}')
        manifest_bytes = archive.read('manifest.json')
        symbols_bytes = archive.read('symbols.json')
        payload_metadata_name = (
            'ir/modules.json' if header['library_version'] == 1 else 'artifacts.json'
        )
        payload_metadata_bytes = archive.read(payload_metadata_name)
        manifest = json.loads(manifest_bytes.decode('utf-8'))
        symbols = json.loads(symbols_bytes.decode('utf-8'))
        metadata = json.loads(payload_metadata_bytes.decode('utf-8'))
    except (OSError, KeyError, UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        raise LibraryError(f'El payload ZIP de {path} no es valido: {error}') from error

    if _sha(manifest_bytes).hex() != header['manifest_sha']:
        raise LibraryError('La SHA del manifest lib1 no coincide')
    if _sha(symbols_bytes).hex() != header['symbols_sha']:
        raise LibraryError('La SHA de simbolos lib1 no coincide')
    if _sha(payload_metadata_bytes).hex() != header['ir_sha']:
        label = 'IR v1' if header['library_version'] == 1 else 'artefactos v2'
        raise LibraryError(f'La SHA de {label} no coincide')
    if symbols.get('mangling') != MANGLE_VERSION:
        raise LibraryError(
            'La libreria lib1 usa una version de mangling incompatible; '
            f'se esperaba {MANGLE_VERSION}'
        )

    manifest_files = manifest.get('files', ())
    if not isinstance(manifest_files, list):
        raise LibraryError('El manifest lib1 no contiene una tabla de archivos valida')
    for item in manifest_files:
        if not isinstance(item, dict):
            raise LibraryError('El manifest contiene una entrada de archivo invalida')
        member = str(item.get('path', ''))
        _safe_member(member)
        try:
            member_data = archive.read(member)
        except KeyError as error:
            raise LibraryError(f'Falta el archivo declarado en el paquete: {member}') from error
        expected_size = int(item.get('size', -1))
        expected_sha = str(item.get('sha256', ''))
        if len(member_data) != expected_size or _sha_hex(member_data) != expected_sha:
            raise LibraryError(f'La SHA del archivo lib1 no coincide: {member}')

    source_files: list[tuple[str, bytes]] = []
    for name in archive.namelist():
        safe = _safe_member(name).as_posix()
        if safe.startswith('source/'):
            source_files.append((safe, archive.read(name)))
    if header['library_version'] == 1:
        if _stable_content_hash(source_files).hex() != header['source_sha']:
            raise LibraryError('La SHA de fuentes lib1 no coincide')
    elif source_files:
        raise LibraryError('Una lib2 no puede contener codigo fuente')
    package_id = str(manifest.get('package_id', ''))
    if package_id != header['package_sha']:
        raise LibraryError('La identidad SHA del paquete lib1 no coincide')
    if str(symbols.get('package_id', '')) != package_id:
        raise LibraryError('La tabla de simbolos lib1 no coincide con el paquete')
    return LibraryPackage(
        path,
        header,
        manifest,
        symbols,
        metadata if header['library_version'] == 1 else {},
        metadata if header['library_version'] == 2 else {},
    ), archive, payload


def _resolve_relative_path(path: str | Path) -> Path:
    caller_dir = Path(os.environ.get('BAGRON_CALLER_DIR', os.getcwd())).resolve()
    target = Path(path)
    if not target.is_absolute():
        return (caller_dir / target).resolve()
    return target.resolve()


def read_library(path: str | Path) -> LibraryPackage:
    package, archive, _ = _load_zip(_resolve_relative_path(path))
    archive.close()
    return package


def _token_value(node: object) -> object | None:
    token = getattr(node, 'token', None)
    return getattr(token, 'value', None)


def _token_data(token: object) -> dict[str, object]:
    token_kind = getattr(getattr(token, 'token', token), 'name', None)
    return {
        'kind': str(token_kind),
        'value': getattr(token, 'value', None),
        'line': getattr(token, 'line', 1),
        'col': getattr(token, 'col', 0),
    }


def _children(node: object) -> list[object]:
    nodes = getattr(node, 'nodes', None)
    if nodes is not None:
        return list(nodes)
    items = getattr(node, 'items', None)
    if items is not None:
        return list(items)
    return []


def _node_data(node: object) -> object:
    class_name = node.__class__.__name__
    if class_name == 'ASTUnaryOp':
        return {
            'kind': 'unary',
            'operator': _token_data(node.operator),
            'operand': _node_data(node.operand),
        }
    if class_name == 'ASTBinaryOp':
        return {
            'kind': 'binary',
            'operator': _token_data(node.operator),
            'left': _node_data(node.left),
            'right': _node_data(node.right),
        }
    if class_name == 'ArrayNode':
        return {
            'kind': 'array',
            'trailing': bool(getattr(node, 'trailing', False)),
            'items': [_node_data(item) for item in node.items],
        }
    if class_name == 'RawNode':
        return {
            'kind': 'raw',
            'text': getattr(node, 'text', ''),
            'tokens': [_token_data(item) for item in node.tokens],
        }
    token = getattr(node, 'token', None)
    token_kind = getattr(getattr(token, 'token', token), 'name', None)
    if token_kind is not None:
        return {
            'kind': 'token',
            'token': _token_data(token),
        }
    name = getattr(node, 'name', None)
    if name is not None:
        return {
            'name': name,
            'nodes': [_node_data(child) for child in _children(node)],
        }
    if isinstance(node, (list, tuple)):
        return [_node_data(child) for child in node]
    return str(node)


def _token_from_data(data: dict[str, object]):
    from gram.core.lexer.tokens import CustomToken, Token, TokenType

    kind = str(data.get('kind', 'UNKNOWN'))
    token = Token.from_string(kind) or CustomToken(kind, kind)
    return TokenType(
        token,
        data.get('value'),
        max(int(data.get('line', 1)) - 1, 0),
        int(data.get('col', 0)),
    )


def _node_from_data(data: object):
    from gram.core.ast.nodes import (
        ASTKeyword,
        ASTRef,
        ASTTokenNode,
        ArrayNode,
        Identifier,
        LiteralNumber,
        LiteralString,
        LiteralSymbol,
        RawNode,
    )
    from gram.core.combinators.expressions import ASTBinaryOp, ASTUnaryOp

    if isinstance(data, list):
        return [_node_from_data(item) for item in data]
    if not isinstance(data, dict):
        return data
    kind = data.get('kind')
    if kind == 'token':
        token_data = data.get('token', {})
        token = _token_from_data(token_data if isinstance(token_data, dict) else {})
        token_kind = getattr(token.token, 'name', '')
        node_type = {
            'STRING': LiteralString,
            'NUMBER': LiteralNumber,
            'DECIMAL': LiteralNumber,
            'IDENT': Identifier,
            'KEYWORD': ASTKeyword,
        }.get(token_kind, LiteralSymbol)
        return node_type(token)
    if kind == 'unary':
        return ASTUnaryOp(
            _token_from_data(data['operator']),
            _node_from_data(data['operand']),
        )
    if kind == 'binary':
        return ASTBinaryOp(
            _node_from_data(data['left']),
            _token_from_data(data['operator']),
            _node_from_data(data['right']),
        )
    if kind == 'array':
        return ArrayNode(
            [_node_from_data(item) for item in data.get('items', ())],
            trailing=bool(data.get('trailing', False)),
        )
    if kind == 'raw':
        return RawNode(
            [_token_from_data(item) for item in data.get('tokens', ())],
            str(data.get('text', '')),
        )
    if 'name' in data:
        return ASTRef(
            str(data['name']),
            [_node_from_data(item) for item in data.get('nodes', ())],
        )
    return data


def _node_name(node: object) -> str | None:
    node_name = getattr(node, 'name', None)
    if node_name == 'FUNCTION':
        signature = next(
            (child for child in _children(node)
             if getattr(child, 'name', None) == 'FUNCTION_SIGNATURE'),
            None,
        )
        node = signature or node
    elif node_name == 'VAR':
        node = next(
            (child for child in _children(node)
             if getattr(child, 'name', None) in {'VAR_DECLARATION', 'VAR_INITIALIZATION'}),
            node,
        )
    elif node_name in {'CLASS', 'STRUCT', 'MOLD', 'FLAGS', 'ENUM', 'OPAQUE'}:
        node = next(
            (child for child in _children(node)
             if getattr(child, 'name', None) == f'{node_name}_SIGNATURE'),
            node,
        )
    if getattr(node, 'token', None) is not None:
        token = getattr(node, 'token', None)
        if getattr(getattr(token, 'token', token), 'name', None) == 'IDENT':
            return str(_token_value(node))
    for child in _children(node):
        found = _node_name(child)
        if found is not None:
            return found
    return None


def _is_private(node: object) -> bool:
    if _token_value(node) == 'private':
        return True
    return any(_is_private(child) for child in _children(node))


def _collect_source_data(source_root: Path, files: list[tuple[str, bytes]]):
    from core.frontend import BAGRON_SESSION
    from core.frontend.aot import AotParser, AotParserError
    from core.compiler.links import extract_link_directives
    from core.compiler import Compiler
    from core.compiler.prep import extract_prep_blocks, preprocess_conditionals
    from core.frontend.tools.imports import public_definition_names

    parser = AotParser.from_config()
    modules: list[dict[str, object]] = []
    symbols: list[dict[str, object]] = []
    targets: dict[str, str] = {}
    main_path = next(
        (
            source_root / candidate
            for candidate in ('main.bg', '_main.bg')
            if (source_root / candidate).is_file()
        ),
        None,
    )
    declared_target = (
        Compiler._read_source_target_clauses(main_path)
        if main_path is not None
        else {}
    )
    target_system = Compiler._normalize_target_system(
        declared_target.get('System')
    )
    target_architecture = Compiler._normalize_target_architecture(
        declared_target.get('Arch')
    )
    for name, data in files:
        if not name.endswith('.bg'):
            continue
        text = data.decode('utf-8')
        source_path = source_root / name
        lines = text.splitlines(keepends=True)
        lines, conditional_errors = preprocess_conditionals(
            lines,
            source_path,
            system=target_system,
            architecture=target_architecture,
        )
        if conditional_errors:
            raise LibraryError('\n'.join(conditional_errors))
        lines, _, link_errors = extract_link_directives(
            lines,
            source_path,
            project_root=source_root,
            allow=True,
        )
        lines, _, library_errors = extract_library_directives(
            lines,
            source_path,
            allow=True,
        )
        # La IR de lib1 conserva los bloques ASM aparte de los nodos GIR para
        # que el consumidor pueda regenerar su objeto con el target actual.
        lines, prep_blocks, prep_errors = extract_prep_blocks(lines, source_path)
        errors = [*link_errors, *library_errors, *prep_errors]
        if errors:
            raise LibraryError('\n'.join(errors))
        try:
            nodes = parser.parse(
                lines,
                session=BAGRON_SESSION,
                name=str(source_path),
            )
        except AotParserError as error:
            raise LibraryError(f'No se pudo analizar {name}: {error}') from error
        modules.append({
            'path': name,
            'nodes': [_node_data(node) for node in nodes],
            'prep_blocks': [
                {
                    'function_name': block.function_name,
                    'dialect': block.dialect,
                    'body': block.body,
                    'line': block.line,
                }
                for block in prep_blocks
            ],
        })
        for node in nodes:
            if getattr(node, 'name', None) == 'CLAUSE':
                children = _children(node)
                if len(children) >= 3:
                    clause = str(_token_value(children[1]))
                    if clause in {'System', 'Arch', 'Boot', 'ABI'}:
                        targets.setdefault(clause, str(_token_value(children[2])))
            if getattr(node, 'name', None) not in {
                'FUNCTION', 'VAR', 'CLASS', 'STRUCT', 'MOLD', 'FLAGS', 'ENUM', 'OPAQUE',
            }:
                continue
            if _is_private(node):
                continue
            symbol_name = _node_name(node)
            if symbol_name is None:
                continue
            symbols.append({
                'name': symbol_name,
                'kind': str(getattr(node, 'name', 'unknown')).lower(),
                'module': name,
                'mangled': symbol_name,
            })
        # Keep the public-definition helper as the single export policy source.
        public_definition_names(nodes)
    return modules, symbols, targets


def _collect_files(source_root: Path) -> list[tuple[str, bytes]]:
    result: list[tuple[str, bytes]] = []
    for path in sorted(source_root.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root).as_posix()
        if relative.startswith('.git/') or relative.startswith('build/'):
            continue
        if relative.startswith('.bagron-cache/'):
            continue
        result.append((relative, path.read_bytes()))
    return result


def _is_reserved_native_path(relative: str | Path) -> bool:
    """Return whether a path belongs to the native-only directories."""
    parts = Path(relative).parts
    return bool(parts and parts[0].lower() in {'libs', 'bins'})


def _collect_link_paths(source_root: Path, files: list[tuple[str, bytes]]) -> list[str]:
    directive = re.compile(r'^\s*#link\s+["\']([^"\']+)["\']\s*$', re.MULTILINE)
    links: set[str] = set()
    for relative, data in files:
        if not relative.endswith('.bg'):
            continue
        text = data.decode('utf-8')
        for raw in directive.findall(text):
            candidate = (source_root / relative).parent / raw
            resolved = candidate.resolve()
            try:
                package_relative = resolved.relative_to(source_root.resolve()).as_posix()
            except ValueError as error:
                raise LibraryError(
                    f'El #link de {relative} sale de la raiz del paquete: {raw!r}'
                ) from error
            links.add(package_relative)
    return sorted(links)


def _validate_source_tree(
    source_root: Path,
    files: list[tuple[str, bytes]],
    link_paths: Sequence[str],
    package_id: str,
):
    """Run Bagron's normal semantic pipeline once while packaging.

    A library does not need a user-facing ``main``.  A temporary entry module
    imports every top-level module so the package records a frontend snapshot
    only after the regular compiler has accepted the source tree.
    """
    from core.compiler import CompilationError, Compiler
    from core.compiler.prep import preprocess_conditionals

    bg_files = [
        relative for relative, _ in files
        if relative.endswith('.bg')
        and not _is_reserved_native_path(relative)
        and Path(relative).name not in {'main.bg', '_main.bg'}
    ]
    if not bg_files:
        return
    with tempfile.TemporaryDirectory(prefix='bagron-lib1-') as temporary:
        root = Path(temporary)
        for relative, data in files:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        module_names: set[str] = set()
        for relative in bg_files:
            module_path = Path(relative)
            if module_path.parent == Path('.'):
                module_names.add(module_path.stem)
            elif module_path.parts[0] == 'modules' and len(module_path.parts) == 2:
                module_names.add(module_path.stem)
            elif (
                module_path.parts[0] == 'modules'
                and len(module_path.parts) == 3
                and module_path.name in {'main.bg', '_main.bg'}
            ):
                module_names.add(module_path.parts[1])
        main_relative = next(
            (
                candidate
                for candidate in ('main.bg', '_main.bg')
                if any(relative == candidate for relative, _ in files)
            ),
            None,
        )
        target_lines: list[str] = []
        library_lines: list[str] = []
        if main_relative is not None:
            main_path = root / main_relative
            declared_target = Compiler._read_source_target_clauses(main_path)
            for clause_name in ('System', 'Arch', 'Boot', 'ABI'):
                clause_value = declared_target.get(clause_name)
                if clause_value is not None:
                    target_lines.append(
                        f'clause {clause_name} "{clause_value}"\n'
                    )

            selected_main, conditional_errors = preprocess_conditionals(
                main_path.read_text(encoding='utf-8').splitlines(keepends=True),
                main_path,
                system=Compiler._normalize_target_system(
                    declared_target.get('System')
                ),
                architecture=Compiler._normalize_target_architecture(
                    declared_target.get('Arch')
                ),
            )
            if conditional_errors:
                raise LibraryError('\n'.join(conditional_errors))
            _, requests, library_errors = extract_library_directives(
                selected_main,
                main_path,
                allow=True,
            )
            if library_errors:
                raise LibraryError('\n'.join(library_errors))
            library_lines = [
                _format_library_directive(request)
                for request in requests
            ]

        if main_relative is None:
            target_lines = [
                'clause System "auto"\n',
                'clause Arch "auto"\n',
            ]
        imports = ''.join(f'import {name}\n' for name in sorted(module_names))
        links = ''.join(f'#link "./{path}"\n' for path in link_paths)
        entry = root / '__bagron_pack_main.bg'
        entry.write_text(
            ''.join(
                [
                    *target_lines,
                    *library_lines,
                    links,
                    imports,
                    'func main() int32:\n    return 0\n',
                ]
            ),
            encoding='utf-8',
        )
        compiler = Compiler()
        compiler.package_identity_override = package_id
        try:
            compiler.compile(entry, executable=False)
        except CompilationError as error:
            raise LibraryError(f'La validacion de la libreria fallo: {error}') from error
        return compiler


def _collect_compiler_symbols(
    compiler,
    source_root: Path,
    package_id: str,
    allowed_modules: set[str] | None = None,
):
    """Serialize the exact symbols assigned by the validating compiler."""
    symbols: list[dict[str, object]] = []
    seen: set[int] = set()
    values = [
        *compiler.storage.functions.values(),
        *compiler.storage.methods.values(),
        *compiler.storage.namespace.values(),
        *compiler.storage.types.values(),
    ]
    for symbol in values:
        if id(symbol) in seen or getattr(symbol, 'privacy', 'public') == 'private':
            continue
        seen.add(id(symbol))
        if getattr(symbol, 'name', None) == 'main':
            continue
        module_path = getattr(symbol, 'module_path', None)
        if module_path is None:
            continue
        try:
            module = Path(module_path).resolve().relative_to(source_root.resolve()).as_posix()
        except ValueError:
            continue
        if (
            module.startswith(('build/', '.bagron/'))
            or Path(module).parts[0] in {'build', '.bagron'}
            or Path(module).name in {'__bagron_pack_main.bg', '__bagron_lib2_main.bg', 'main.bg', '_main.bg'}
        ):
            continue
        if allowed_modules is not None and module not in allowed_modules:
            continue
        if isinstance(symbol, FunctionSymbol):
            kind = 'method' if symbol.is_method else 'function'
            name = symbol.source_name if symbol.is_method else symbol.name
        elif isinstance(symbol, Variable):
            kind = 'variable'
            name = symbol.name
        elif isinstance(symbol, EnumSymbol):
            kind = 'enum'
            name = symbol.name
        elif isinstance(symbol, OpaqueSymbol):
            kind = 'opaque'
            name = symbol.name
        elif isinstance(symbol, AggregateSymbol):
            kind = 'type'
            name = symbol.name
        else:
            continue
        item = {
            'name': name,
            'public': name,
            'kind': kind,
            'module': module,
            'llvm': getattr(symbol, 'llvm_name', None) or name,
            'package_id': package_id,
        }
        if isinstance(symbol, FunctionSymbol):
            item['decorators'] = list(symbol.decorators)
            item['is_inline'] = bool(symbol.is_inline)
            if symbol.is_method:
                item['owner'] = symbol.owner_type
                item['is_static'] = bool(symbol.is_static)
        signature = getattr(symbol, 'signature', None)
        if signature is not None:
            item['signature'] = _serialize_signature(signature)
        type_spec = getattr(symbol, 'type_spec', None)
        if type_spec is not None:
            item['type'] = _serialize_type_spec(type_spec)
            value_info = getattr(symbol, 'value_info', None)
            if value_info is not None and getattr(value_info, 'is_literal', False):
                item['value'] = value_info.value
        if isinstance(symbol, OpaqueSymbol):
            item['representation'] = _serialize_type_spec(symbol.representation)
        symbols.append(item)
    return sorted(
        symbols,
        key=lambda item: (
            str(item['module']), str(item['kind']), str(item['name'])
        ),
    )


def _serialize_type_spec(spec: object) -> dict[str, object]:
    return {
        'name': str(getattr(spec, 'name', 'void')),
        'bit_width': getattr(spec, 'bit_width', None),
        'signed': getattr(spec, 'signed', None),
        'pointer_level': int(getattr(spec, 'pointer_level', 0)),
        'array_depth': int(getattr(spec, 'array_depth', 0)),
        'array_lengths': list(getattr(spec, 'array_lengths', ()) or ()),
        'value_is_const': bool(getattr(spec, 'value_is_const', False)),
        'pointer_is_const': bool(getattr(spec, 'pointer_is_const', False)),
    }


def _serialize_signature(signature: object) -> dict[str, object]:
    parameters = []
    for parameter in getattr(signature, 'parameters', ()):
        parameters.append({
            'name': str(getattr(parameter, 'name', 'arg')),
            'type': _serialize_type_spec(getattr(parameter, 'type_spec', None)),
            'is_length': bool(getattr(parameter, 'is_length', False)),
            'is_size': bool(getattr(parameter, 'is_size', False)),
            'is_signed': bool(getattr(parameter, 'is_signed', False)),
            'is_region': bool(getattr(parameter, 'is_region', False)),
            'is_receiver': bool(getattr(parameter, 'is_receiver', False)),
            'is_unique': bool(getattr(parameter, 'is_unique', False)),
            'length_of': getattr(parameter, 'length_of', None),
            'signed_of': getattr(parameter, 'signed_of', None),
            'region_of': getattr(parameter, 'region_of', None),
        })
    return {
        'parameters': parameters,
        'return': _serialize_type_spec(getattr(signature, 'return_type', None)),
    }


def compute_library_signature(
    source_root: str | Path,
    *,
    author: str | None = None,
    name: str | None = None,
    version: str | None = None,
) -> tuple[str, str]:
    """Calcula la firma canónica SHA-256 de una librería basada en sus fuentes .bg y metadata."""
    root = _resolve_relative_path(source_root)
    if root.is_file():
        root = root.parent
    if not root.is_dir():
        raise LibraryError(f'La ruta especificada no es un directorio: {root}')

    meta_path = root / 'meta.toml'
    meta_data: dict[str, object] = {}
    if meta_path.is_file():
        try:
            meta_data = tomllib.loads(meta_path.read_text(encoding='utf-8'))
        except Exception as exc:
            raise LibraryError(f'Error al leer {meta_path}: {exc}') from exc

    pkg_name = name or (meta_data.get('package', {}) if isinstance(meta_data.get('package'), dict) else {}).get('name') or root.name
    pkg_ver = version or (meta_data.get('package', {}) if isinstance(meta_data.get('package'), dict) else {}).get('version') or '0.1.0'
    author_name = author or (meta_data.get('author', {}) if isinstance(meta_data.get('author'), dict) else {}).get('name') or 'Discentra Community'

    bg_files: list[tuple[str, bytes]] = []
    for path in sorted(root.rglob('*.bg')):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if _is_reserved_native_path(rel):
            continue
        if rel.startswith('.git/') or rel.startswith('build/') or rel.startswith('.bagron-cache/'):
            continue
        bg_files.append((rel, path.read_bytes()))

    if not bg_files:
        raise LibraryError(f'No se encontraron archivos .bg en {root}')

    source_digest = hashlib.sha256()
    for rel_path, data in sorted(bg_files, key=lambda item: item[0]):
        source_digest.update(rel_path.encode('utf-8'))
        source_digest.update(b'\0')
        source_digest.update(data)
    source_sha = source_digest.hexdigest()

    sig_digest = hashlib.sha256()
    sig_digest.update(str(author_name).encode('utf-8'))
    sig_digest.update(b'\0')
    sig_digest.update(str(pkg_name).encode('utf-8'))
    sig_digest.update(b'\0')
    sig_digest.update(str(pkg_ver).encode('utf-8'))
    sig_digest.update(b'\0')
    sig_digest.update(source_sha.encode('utf-8'))

    signature = f'sha256:{sig_digest.hexdigest()}'
    return signature, source_sha


def sign_library_metadata(
    source_root: str | Path,
    *,
    author: str | None = None,
    name: str | None = None,
    version: str | None = None,
) -> str:
    """Firma el meta.toml de la librería in-place y devuelve la firma generada."""
    root = _resolve_relative_path(source_root)
    if root.is_file():
        root = root.parent
    meta_path = root / 'meta.toml'
    if not meta_path.is_file():
        raise LibraryError(f'No se encontró meta.toml en {root}')

    signature, _ = compute_library_signature(
        root, author=author, name=name, version=version
    )
    text = meta_path.read_text(encoding='utf-8')
    if re.search(r'^\s*signature\s*=', text, re.MULTILINE):
        new_text = re.sub(
            r'^\s*signature\s*=\s*("[^"]*"|\'[^\']*\')',
            f'signature = "{signature}"',
            text,
            flags=re.MULTILINE,
        )
    elif '[author]' in text:
        new_text = re.sub(
            r'(\[author\][^\n]*\n)',
            rf'\1signature = "{signature}"\n',
            text,
            count=1,
        )
    else:
        new_text = text.rstrip() + f'\n\n[author]\nsignature = "{signature}"\n'

    meta_path.write_text(new_text, encoding='utf-8')
    return signature


def verify_library_signature(source_root: str | Path) -> tuple[bool, str]:
    """Verifica si la firma declarada en meta.toml coincide con los fuentes y metadatos reales."""
    root = _resolve_relative_path(source_root)
    if root.is_file():
        root = root.parent
    meta_path = root / 'meta.toml'
    if not meta_path.is_file():
        return False, f'No se encontró meta.toml en {root}'

    try:
        data = tomllib.loads(meta_path.read_text(encoding='utf-8'))
    except Exception as exc:
        return False, f'Error al leer meta.toml: {exc}'

    declared_sig = data.get('author', {}).get('signature', '').strip() if isinstance(data.get('author'), dict) else ''
    if not declared_sig:
        return False, 'meta.toml no declara una firma de autor ([author].signature)'

    try:
        expected_sig, _ = compute_library_signature(root)
    except LibraryError as exc:
        return False, str(exc)

    if declared_sig != expected_sig:
        return False, f'Firma inválida. Declarada: {declared_sig}, Calculada: {expected_sig}'

    return True, expected_sig


def _zip_path(relative: str) -> str:
    if relative.startswith('bins/') or relative.startswith('libs/'):
        return relative
    return f'source/{relative}'


def pack_library(
    source: str | Path,
    output: str | Path,
    *,
    name: str | None = None,
    version: str = '0.1.0',
) -> Path:
    source_root = _resolve_relative_path(source)
    if source_root.is_file():
        source_root = source_root.parent
    if not source_root.is_dir():
        raise LibraryError(f'La fuente de la libreria no es un directorio: {source_root}')

    meta_path = source_root / 'meta.toml'
    if meta_path.is_file():
        try:
            meta_data = tomllib.loads(meta_path.read_text(encoding='utf-8'))
            pkg_data = meta_data.get('package', {}) if isinstance(meta_data.get('package'), dict) else {}
            if name is None and 'name' in pkg_data:
                name = str(pkg_data['name'])
            if version == '0.1.0' and 'version' in pkg_data:
                version = str(pkg_data['version'])
        except Exception:
            pass
        try:
            sign_library_metadata(source_root, name=name, version=version)
        except Exception:
            pass

    files = _collect_files(source_root)
    output_path = _resolve_relative_path(output)
    files = [
        (relative, data)
        for relative, data in files
        if (source_root / relative).resolve() != output_path
    ]
    misplaced_sources = [
        name for name, _ in files
        if name.endswith('.bg') and _is_reserved_native_path(name)
    ]
    if misplaced_sources:
        raise LibraryError(
            'Los archivos .bg deben estar en modules/ o en la raiz de fuentes; '
            f'no se permiten en libs/ ni bins/: {misplaced_sources[0]}'
        )
    bg_files = [
        (name, data) for name, data in files
        if name.endswith('.bg') and not _is_reserved_native_path(name)
    ]
    if not bg_files:
        raise LibraryError('La libreria no contiene archivos .bg')
    package_name = name or source_root.name
    link_paths = _collect_link_paths(source_root, files)
    source_files = [
        (f'source/{relative}', data)
        for relative, data in files
        if not (relative.startswith('bins/') or relative.startswith('libs/'))
    ]
    source_sha = _stable_content_hash(source_files)
    package_id = package_identity(package_name, version, source_sha.hex())
    compiler = _validate_source_tree(
        source_root,
        files,
        link_paths,
        package_id,
    )
    allowed_modules = {
        Path(relative).as_posix() for relative, _ in bg_files
        if Path(relative).name not in {'main.bg', '_main.bg'}
    }
    modules, _, targets = _collect_source_data(source_root, bg_files)
    symbols = _collect_compiler_symbols(
        compiler,
        compiler.project_root,
        package_id,
        allowed_modules=allowed_modules,
    )
    symbol_payload = {
        'format': 1,
        'library_version': 1,
        'kind': 'source',
        'mangling': MANGLE_VERSION,
        'package_id': package_id,
        'exports': symbols,
    }
    ir_payload = {
        'format': 1,
        'modules': modules,
    }
    symbols_bytes = _json_bytes(symbol_payload)
    ir_bytes = _json_bytes(ir_payload)
    manifest = {
        'format': 'bagron-library',
        'library_version': 1,
        'kind': 'source',
        'version': version,
        'name': package_name,
        'package_id': package_id,
        'targets': targets,
        'modules': [
            f'source/{relative}' for relative, _ in bg_files
            if Path(relative).name not in {'main.bg', '_main.bg'}
        ],
        'files': [
            {'path': _zip_path(relative), 'sha256': _sha_hex(data), 'size': len(data)}
            for relative, data in files
        ],
        'source_sha256': source_sha.hex(),
        'links': link_paths,
    }
    manifest_bytes = _json_bytes(manifest)
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, data in files:
            info = zipfile.ZipInfo(_zip_path(relative))
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
        archive.writestr('manifest.json', manifest_bytes)
        archive.writestr('symbols.json', symbols_bytes)
        archive.writestr('ir/modules.json', ir_bytes)
    zip_bytes = payload.getvalue()
    package_sha = bytes.fromhex(package_id)
    header = HEADER.pack(
        MAGIC,
        FORMAT_MAJOR,
        FORMAT_MINOR,
        KIND_LIB1,
        0,
        HEADER.size,
        HEADER.size,
        len(zip_bytes),
        _sha(manifest_bytes),
        _sha(symbols_bytes),
        _sha(ir_bytes),
        source_sha,
        package_sha,
    )
    destination = output_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(header + zip_bytes)
    return destination


def pack_compiled_library(
    source: str | Path,
    output: str | Path,
    *,
    name: str | None = None,
    version: str = '0.1.0',
) -> Path:
    """Compile a source tree into a target-specific lib2 container.

    Unlike lib1, the archive contains no source or frontend IR.  It carries
    one native Bagron object plus the native files required by its declared
    external links.  The public symbol table remains available for inspection
    and for a future native/API importer.
    """
    from core.compiler import CompilationError, Compiler
    from core.backend.llvm.module import BackendError, LLVMBackend

    source_root = _resolve_relative_path(source)
    if source_root.is_file():
        source_root = source_root.parent
    if not source_root.is_dir():
        raise LibraryError(f'La fuente de la libreria no es un directorio: {source_root}')

    meta_path = source_root / 'meta.toml'
    if meta_path.is_file():
        try:
            meta_data = tomllib.loads(meta_path.read_text(encoding='utf-8'))
            pkg_data = meta_data.get('package', {}) if isinstance(meta_data.get('package'), dict) else {}
            if name is None and 'name' in pkg_data:
                name = str(pkg_data['name'])
            if version == '0.1.0' and 'version' in pkg_data:
                version = str(pkg_data['version'])
        except Exception:
            pass
        try:
            sign_library_metadata(source_root, name=name, version=version)
        except Exception:
            pass

    files = _collect_files(source_root)
    output_path = _resolve_relative_path(output)
    files = [
        (relative, data)
        for relative, data in files
        if (source_root / relative).resolve() != output_path
    ]
    misplaced_sources = [
        relative for relative, _ in files
        if relative.endswith('.bg') and _is_reserved_native_path(relative)
    ]
    if misplaced_sources:
        raise LibraryError(
            'Los archivos .bg deben estar en modules/ o en la raiz de fuentes; '
            f'no se permiten en libs/ ni bins/: {misplaced_sources[0]}'
        )
    bg_files = [
        relative for relative, _ in files
        if relative.endswith('.bg')
        and not _is_reserved_native_path(relative)
        and Path(relative).name not in {'main.bg', '_main.bg'}
    ]
    if not bg_files:
        raise LibraryError('La lib2 no contiene modulos .bg compilables')

    package_name = name or source_root.name
    source_sha = _stable_content_hash(files)
    # Target clauses are part of the input hash, so changing a target creates
    # a different package identity even when the source text is otherwise the
    # same.
    _, _, targets = _collect_source_data(
        source_root,
        [item for item in files if item[0].endswith('.bg')],
    )
    target_identity = _json_bytes(targets)
    package_id = package_identity(
        package_name,
        version,
        source_sha.hex() + target_identity.hex(),
    )

    with tempfile.TemporaryDirectory(prefix='bagron-lib2-') as temporary:
        root = Path(temporary)
        for relative, data in files:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)

        module_names: set[str] = set()
        for relative in bg_files:
            module_path = Path(relative)
            if module_path.parent == Path('.'):
                module_names.add(module_path.stem)
            elif module_path.parts[0] == 'modules' and len(module_path.parts) == 2:
                module_names.add(module_path.stem)
            elif (
                module_path.parts[0] == 'modules'
                and len(module_path.parts) == 3
                and module_path.name in {'main.bg', '_main.bg'}
            ):
                module_names.add(module_path.parts[1])
        if len(module_names) != len(bg_files):
            raise LibraryError(
                'La lib2 solo admite modulos .bg directos en la raiz o modules/'
            )

        clauses = ''.join(
            f"clause {key} '{value}'\n"
            for key, value in sorted(targets.items())
        )
        links = ''.join(
            f'#link "./{directory}"\n'
            for directory in ('bins', 'libs')
            if (root / directory).is_dir()
        )
        entry = root / '__bagron_lib2_main.bg'
        entry.write_text(
            clauses
            + links
            + ''.join(f'import {module}\n' for module in sorted(module_names)),
            encoding='utf-8',
        )

        compiler = Compiler()
        compiler.package_identity_override = package_id
        try:
            compiler.compile(entry, executable=False, require_main=False)
            build_root = root / 'build'
            object_path, target_triple = LLVMBackend().emit_object(
                compiler.storage,
                build_root,
                stem=package_name,
            )
        except (CompilationError, BackendError) as error:
            raise LibraryError(f'La compilacion de la lib2 fallo: {error}') from error

        allowed_modules = {
            Path(relative).as_posix() for relative, _ in files
            if relative.endswith('.bg')
            and not _is_reserved_native_path(relative)
            and Path(relative).name not in {'main.bg', '_main.bg', '__bagron_lib2_main.bg'}
        }
        symbols = _collect_compiler_symbols(
            compiler,
            root,
            package_id,
            allowed_modules=allowed_modules,
        )
        object_relative = f'objects/{object_path.name}'
        artifact_files: list[tuple[str, bytes]] = [
            (object_relative, object_path.read_bytes())
        ]
        native_extensions = {
            '.a', '.lib', '.dll', '.so', '.dylib', '.o', '.obj', '.wasm'
        }
        for relative, data in files:
            if not (relative.startswith('bins/') or relative.startswith('libs/')):
                continue
            if Path(relative).suffix.lower() not in native_extensions:
                continue
            artifact_files.append((relative, data))

        artifacts = {
            'format': 1,
            'target_triple': target_triple,
            'object': object_relative,
            'native': [relative for relative, _ in artifact_files[1:]],
        }
        manifest = {
            'format': 'bagron-library',
            'library_version': 2,
            'kind': 'compiled',
            'name': package_name,
            'version': version,
            'package_id': package_id,
            'target': {
                'triple': target_triple,
                'System': str(compiler.storage.system),
                'Arch': str(compiler.storage.architecture),
            },
            'native_links': list(compiler.storage.native_links),
            'files': [
                {
                    'path': relative,
                    'sha256': _sha_hex(data),
                    'size': len(data),
                }
                for relative, data in artifact_files
            ],
        }
        symbols_payload = {
            'format': 2,
            'kind': 'compiled',
            'library_version': 2,
            'mangling': MANGLE_VERSION,
            'package_id': package_id,
            'exports': symbols,
        }
        manifest_bytes = _json_bytes(manifest)
        symbols_bytes = _json_bytes(symbols_payload)
        artifacts_bytes = _json_bytes(artifacts)

    payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, data in artifact_files:
            info = zipfile.ZipInfo(relative)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
        archive.writestr('manifest.json', manifest_bytes)
        archive.writestr('symbols.json', symbols_bytes)
        archive.writestr('artifacts.json', artifacts_bytes)
    zip_bytes = payload.getvalue()
    header = HEADER.pack(
        MAGIC,
        FORMAT_MAJOR,
        FORMAT_MINOR,
        KIND_LIB2,
        0,
        HEADER.size,
        HEADER.size,
        len(zip_bytes),
        _sha(manifest_bytes),
        _sha(symbols_bytes),
        _sha(artifacts_bytes),
        source_sha,
        bytes.fromhex(package_id),
    )
    destination = output_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(header + zip_bytes)
    return destination


def verify_library(path: str | Path) -> LibraryPackage:
    package = read_library(path)
    for item in package.manifest.get('files', ()):
        if not isinstance(item, dict):
            raise LibraryError('El manifest contiene una entrada de archivo invalida')
        name = str(item.get('path', ''))
        _safe_member(name)
    return package


def inspect_library(path: str | Path) -> dict[str, object]:
    package = verify_library(path)
    return {
        'header': package.header,
        'kind': package.kind,
        'format': 'lib2' if package.kind == 'compiled' else 'lib1',
        'library_version': package.library_version,
        'manifest': package.manifest,
        'exports': package.symbols.get('exports', []),
        'ir_modules': [item.get('path') for item in package.ir.get('modules', [])],
        'artifacts': package.artifacts,
    }


def unpack_library(path: str | Path, destination: str | Path) -> Path:
    package, archive, _ = _load_zip(_resolve_relative_path(path))
    target = _resolve_relative_path(destination)
    target.mkdir(parents=True, exist_ok=True)
    try:
        for name in archive.namelist():
            safe = _safe_member(name)
            output = (target / Path(*safe.parts)).resolve()
            if target not in output.parents and output != target:
                raise LibraryError(f'La ruta del paquete escapa de destino: {name!r}')
            if name.endswith('/'):
                output.mkdir(parents=True, exist_ok=True)
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.read(name))
    finally:
        archive.close()
    return target


def extract_library(path: str | Path, cache_root: str | Path) -> tuple[LibraryPackage, Path]:
    package, archive, _ = _load_zip(Path(path).resolve())
    destination = Path(cache_root).resolve() / package.package_id
    marker = destination / '.complete'
    if not marker.is_file():
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True, exist_ok=True)
        try:
            for name in archive.namelist():
                safe = _safe_member(name)
                output = (destination / Path(*safe.parts)).resolve()
                if destination not in output.parents and output != destination:
                    raise LibraryError(f'La ruta del paquete escapa de cache: {name!r}')
                if name.endswith('/'):
                    output.mkdir(parents=True, exist_ok=True)
                else:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(archive.read(name))
            marker.write_text(package.package_id, encoding='ascii')
        finally:
            archive.close()
    else:
        archive.close()
    return package, destination


_LIBRARY_DIRECTIVE = re.compile(
    r'^[ \t]*library[ \t]+'
    r'(?:(?P<quote>["\'])(?P<path>.*?)(?P=quote)|'
    r'(?P<global>[A-Za-z_][A-Za-z0-9_]*))'
    r'[ \t]+as[ \t]+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)[ \t]*$'
)


def extract_library_directives(
    lines: Sequence[str],
    source: Path,
    *,
    allow: bool,
) -> tuple[list[str], list[LibraryRequest], list[str]]:
    transformed: list[str] = []
    requests: list[LibraryRequest] = []
    errors: list[str] = []
    for index, line in enumerate(lines):
        raw = line.rstrip('\r\n')
        if not raw.lstrip().startswith('library'):
            transformed.append(line)
            continue
        match = _LIBRARY_DIRECTIVE.fullmatch(raw)
        if not allow:
            errors.append(
                f'{source}:{index + 1}: library solo se permite en el modulo principal'
            )
            transformed.append('\n' if line.endswith(('\n', '\r')) else '')
            continue
        if match is None:
            errors.append(
                f'{source}:{index + 1}: library requiere "ruta.lib" o '
                'nombre_global as Alias'
            )
            transformed.append('\n' if line.endswith(('\n', '\r')) else '')
            continue
        global_name = match.group('global')
        requests.append(LibraryRequest(
            global_name if global_name is not None else match.group('path'),
            match.group('alias'),
            source.resolve(),
            global_name=global_name is not None,
        ))
        transformed.append('\n' if line.endswith(('\n', '\r')) else '')
    return transformed, requests, errors


def resolve_library_path(
    name: str,
    source: Path,
    project_root: Path,
    *,
    global_name: bool = False,
) -> Path | None:
    if global_name:
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) is None:
            return None
        from core.globvars import BAGRON_ROOT

        candidate = Path(f'{name}.lib')
        roots = [BAGRON_ROOT.resolve() / 'libs']
    else:
        candidate = Path(name)
        if candidate.is_absolute():
            return None
        from core.globvars import BAGRON_ROOT

        # ``library`` checks project-local libs, package-local libs for extracted
        # dependencies, and falls back to canonical Bagron libs.
        roots = [
            project_root.resolve() / 'libs',
            source.parent.parent.resolve() / 'libs',
            source.parent.resolve() / 'libs',
            BAGRON_ROOT.resolve() / 'libs',
        ]

    seen: set[Path] = set()
    for root in roots:
        root = root.resolve()
        resolved = (root / candidate).resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file() and resolved.suffix.lower() == '.lib':
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            return resolved
    return None


__all__ = [
    'LibraryError',
    'LibraryPackage',
    'LibraryRequest',
    'compute_library_signature',
    'extract_library',
    'extract_library_directives',
    'inspect_library',
    'pack_library',
    'pack_compiled_library',
    'read_library',
    'resolve_library_path',
    'sign_library_metadata',
    'unpack_library',
    'verify_library',
    'verify_library_signature',
]

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from core.compiler import Compiler


@dataclass(frozen=True)
class ImportRequest:
    module: str
    alias: str | None = None
    selected: tuple[tuple[str, str], ...] = ()
    target: Path | None = None
from gram import ast as gast


def _children(node: object) -> list[object]:
    if isinstance(node, list):
        return list(node)
    nodes = getattr(node, 'nodes', None)
    if nodes is not None:
        return list(nodes)
    items = getattr(node, 'items', None)
    if items is not None:
        return list(items)
    return []


def _token_kind(node: object) -> str | None:
    token = getattr(node, 'token', None)
    token = getattr(token, 'token', token)
    return getattr(token, 'name', None)


def _token_value(node: object) -> object | None:
    token = getattr(node, 'token', None)
    return getattr(token, 'value', None)


def _tokens(node: object) -> Iterable[object]:
    if _token_kind(node) is not None:
        yield node
    for child in _children(node):
        yield from _tokens(child)


def module_name(node: gast.ASTRef) -> str | None:
    tokens = list(_tokens(node))
    for index, token in enumerate(tokens):
        if _token_value(token) == 'from':
            for candidate in tokens[index + 1:]:
                if _token_kind(candidate) == 'IDENT':
                    return str(_token_value(candidate))
            return None

    seen_import = False
    for token in tokens:
        if _token_value(token) == 'import':
            seen_import = True
            continue
        if seen_import and _token_kind(token) == 'IDENT':
            return str(_token_value(token))
    return None


def parse_request(node: gast.ASTRef, target: Path | None = None) -> ImportRequest | None:
    tokens = list(_tokens(node))
    name = module_name(node)
    if name is None:
        return None

    from_index = next(
        (index for index, token in enumerate(tokens)
         if _token_value(token) == 'from'),
        None,
    )
    if from_index is not None:
        selected: list[tuple[str, str]] = []
        index = 0
        while index < from_index:
            token = tokens[index]
            if _token_kind(token) != 'IDENT':
                index += 1
                continue
            source = str(_token_value(token))
            local = source
            if (
                index + 2 < from_index
                and _token_value(tokens[index + 1]) == 'as'
                and _token_kind(tokens[index + 2]) == 'IDENT'
            ):
                local = str(_token_value(tokens[index + 2]))
                index += 3
            else:
                index += 1
            selected.append((source, local))
        return ImportRequest(name, selected=tuple(selected), target=target)

    import_index = next(
        (index for index, token in enumerate(tokens)
         if _token_value(token) == 'import'),
        None,
    )
    if import_index is None:
        return ImportRequest(name, target=target)

    alias = None
    for index in range(import_index + 1, len(tokens) - 1):
        if (
            _token_value(tokens[index]) == 'as'
            and _token_kind(tokens[index + 1]) == 'IDENT'
        ):
            alias = str(_token_value(tokens[index + 1]))
            break
    return ImportRequest(name, alias=alias, target=target)


def _first_identifier(node: object) -> str | None:
    if _token_kind(node) == 'IDENT':
        return str(_token_value(node))
    for child in _children(node):
        found = _first_identifier(child)
        if found is not None:
            return found
    return None


def _is_public(node: object) -> bool:
    body_names = {
        'FUNCTION_BODY', 'STRUCT_BODY', 'FLAGS_BODY', 'MOLD_BODY',
        'ENUM_BODY', 'CLASS_BODY', 'EXTERN_BODY',
    }

    def visit(current: object) -> bool:
        if _token_value(current) == 'private':
            return False
        for child in _children(current):
            if getattr(child, 'name', None) in body_names:
                break
            if not visit(child):
                return False
        return True

    return visit(node)


def public_definition_names(nodes: list[gast.ASTRef]) -> set[str]:
    definitions = {
        'FUNCTION', 'VAR', 'CLASS', 'STRUCT', 'MOLD', 'FLAGS', 'ENUM',
        'TYPEALIAS',
    }
    names = {
        name
        for node in nodes
        if node.name in definitions and _is_public(node)
        if (name := _first_identifier(node)) is not None
    }

    def extern_names(node: object) -> set[str]:
        if getattr(node, 'name', None) == 'EXTERN_FUNCTION':
            name = _first_identifier(node)
            return {name} if name is not None else set()
        names: set[str] = set()
        for child in _children(node):
            names.update(extern_names(child))
        return names

    for node in nodes:
        if node.name != 'EXTERN' or not _is_public(node):
            continue
        names.update(extern_names(node))
    return names


def bind_aliases(compiler: Compiler) -> None:
    """Bind qualified and selective imports after all module symbols collect."""
    for request in compiler.import_requests:
        if request.target is None:
            continue
        exports = compiler.module_exports.get(request.target, set())
        if request.selected:
            bindings = request.selected
        elif request.alias:
            bindings = tuple((name, f'{request.alias}.{name}') for name in exports)
        else:
            bindings = tuple((name, name) for name in exports)

        for source_name, local_name in bindings:
            if source_name not in exports:
                compiler.error(
                    f'El simbolo {source_name} no es publico en el modulo '
                    f'{request.module}'
                )
                continue
            symbol = compiler.storage.functions.get(source_name)
            if symbol is not None:
                existing = compiler.storage.functions.get(local_name)
                if existing is not None and existing is not symbol:
                    compiler.error(f'El simbolo importado ya existe: {local_name}')
                    continue
                compiler.storage.functions[local_name] = symbol
                if local_name != source_name:
                    compiler.storage.function_aliases[local_name] = source_name
                continue

            variable = compiler.storage.namespace.get(source_name)
            if variable is not None and local_name != source_name:
                compiler.storage.variable_aliases[local_name] = variable
                continue

            type_symbol = compiler.storage.types.get(source_name)
            if type_symbol is not None and local_name != source_name:
                compiler.storage.type_aliases[local_name] = source_name


def _candidate_paths(name: str, current_file: Path, project_root: Path) -> list[Path]:
    relative = Path(name)
    if relative.suffix and relative.suffix != '.bg':
        return []

    filename = relative if relative.suffix == '.bg' else relative.with_suffix('.bg')
    roots = [
        current_file.parent,
        project_root,
        project_root / 'lib',
        project_root / 'libs',
    ]
    candidates: list[Path] = []
    for root in roots:
        candidates.append(root / filename)
        candidates.append(root / relative / 'main.bg')
    return candidates


def resolve_module_path(
    compiler: Compiler,
    name: str,
    current_file: Path,
) -> Path | None:
    project_root = compiler.project_root
    if project_root is None:
        project_root = current_file.parent

    for candidate in _candidate_paths(name, current_file, project_root):
        if candidate.is_file() and candidate.suffix == '.bg':
            return candidate.resolve()

    compiler.error(
        f'No se encontro el modulo Bagron {name!r} desde {current_file}'
    )
    return None


def validate(compiler: Compiler, node: gast.ASTRef):
    """Imports are loaded before semantic processing by the module loader."""
    name = module_name(node)
    if name is None:
        compiler.error('La declaracion import no contiene un modulo valido')
    return node


__all__ = [
    'ImportRequest',
    'bind_aliases',
    'module_name',
    'parse_request',
    'public_definition_names',
    'resolve_module_path',
    'validate',
]

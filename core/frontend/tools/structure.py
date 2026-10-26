from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from core.frontend.handles import handle_declaration
from core.frontend.objects import AggregateSymbol, FieldSpec
from core.frontend.syntax.keywords import INTRINSIC_TYPES
from core.frontend.tools.types import (
    INTEGER_TYPES,
    TypeResolutionError,
    UnsupportedExpressionError,
    ValueResolutionError,
    infer_value,
    is_compatible,
    resolve_type,
)
from gram import ast as gast

if TYPE_CHECKING:
    from core.compiler import Compiler


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


def _find_identifier(node: object) -> str | None:
    if _token_kind(node) == 'IDENT':
        return str(_token_value(node))
    for child in _children(node):
        found = _find_identifier(child)
        if found is not None:
            return found
    return None


def _find_all(node: object, names: set[str]) -> Iterable[gast.ASTRef]:
    if isinstance(node, gast.ASTRef):
        if node.name in names:
            yield node
        for child in node.nodes:
            yield from _find_all(child, names)
    elif isinstance(node, list):
        for child in node:
            yield from _find_all(child, names)


def _privacy(node: object) -> str:
    for child in _children(node):
        value = _token_value(child)
        if value in ('public', 'private'):
            return str(value)
        if isinstance(child, gast.ASTRef):
            found = _privacy(child)
            if found != 'public':
                return found
    return 'public'


def _signature(node: gast.ASTRef) -> gast.ASTRef | None:
    return next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef)
            and child.name.endswith('_SIGNATURE')
        ),
        None,
    )


def _body(node: gast.ASTRef) -> gast.ASTRef | None:
    return next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef)
            and child.name.endswith('_BODY')
        ),
        None,
    )


def _pending_modifiers(node: gast.ASTRef) -> tuple[str, ...]:
    found: list[str] = []
    for child in _find_all(node, {'PACKED_DECORATOR', 'ATTRIBUTES', 'ALIGNEMENT'}):
        if child.name == 'PACKED_DECORATOR':
            if '@packed' not in found:
                found.append('@packed')
        elif '__align__' not in found:
            found.append('__align__')

    for child in _children(node):
        if _token_value(child) == 'volatile':
            if 'volatile' not in found:
                found.append('volatile')
        if isinstance(child, gast.ASTRef):
            for modifier in _pending_modifiers(child):
                if modifier not in found:
                    found.append(modifier)
    return tuple(found)


def _register_node(compiler: Compiler, node: gast.ASTRef) -> None:
    signature = _signature(node)
    name = _find_identifier(signature) if signature is not None else None
    if not name:
        compiler.error(f'La declaracion {node.name.lower()} no tiene nombre')
        return

    symbol = AggregateSymbol(
        name=name,
        kind=node.name.lower(),
        privacy=_privacy(signature) if signature is not None else 'public',
    )
    if not compiler.storage.define_type(symbol):
        compiler.error(f'El tipo ya fue declarado: {name}')
        return
    compiler.type_bindings[id(node)] = symbol


def collect(compiler: Compiler, nodes: list[gast.ASTRef]) -> None:
    """Register aggregate names before any field is validated."""
    for node in nodes:
        if node.name in ('STRUCT', 'MOLD', 'FLAGS'):
            _register_node(compiler, node)


def _known_field_type(compiler: Compiler, type_spec) -> bool:
    if type_spec.name in INTRINSIC_TYPES:
        return type_spec.name not in {'void', 'Null'}
    return compiler.storage.resolve_type(type_spec.name) is not None


def _field_nodes(body: gast.ASTRef) -> list[gast.ASTRef]:
    return list(_find_all(body, {'VAR_INITIALIZATION', 'VAR_DECLARATION'}))


def _resolve_field_type(compiler: Compiler, handle, owner: str):
    try:
        type_spec = resolve_type(
            handle.type_node,
            pointer_level=handle.pointer_level,
            pointer_is_const=handle.pointer_is_const,
        )
    except TypeResolutionError as error:
        compiler.error(f'{owner}.{handle.name}: {error}')
        return None

    if not _known_field_type(compiler, type_spec):
        compiler.error(
            f'El tipo de {owner}.{handle.name} no existe: '
            f'{type_spec.canonical_name}'
        )
        return None
    return type_spec


def _validate_flags_value(compiler: Compiler, owner: str, handle, type_spec):
    if (
        type_spec.pointer_level
        or type_spec.array_depth
        or type_spec.name not in INTEGER_TYPES
    ):
        compiler.error(
            f'El campo {owner}.{handle.name} debe usar un tipo entero escalar'
        )
        return None

    try:
        value_info = infer_value(handle.value_node, compiler.storage.resolve)
    except (UnsupportedExpressionError, ValueResolutionError) as error:
        compiler.error(f'{owner}.{handle.name}: {error}')
        return None

    if not value_info.is_literal or value_info.type_spec.name != 'int':
        compiler.error(
            f'El valor de {owner}.{handle.name} debe ser un literal entero'
        )
        return None

    if not is_compatible(type_spec, value_info):
        compiler.error(
            f'El valor de {owner}.{handle.name} no coincide con '
            f'{type_spec.canonical_name}'
        )
        return None
    return value_info


def validate(compiler: Compiler, node: gast.ASTRef):
    """Validate fields while keeping aggregate definitions semantic-only."""
    symbol = compiler.type_bindings.get(id(node))
    if not isinstance(symbol, AggregateSymbol):
        return node

    for pending in _pending_modifiers(node):
        compiler.error(
            f'{pending} aun no esta implementado para el tipo {symbol.name}'
        )

    body = _body(node)
    if body is None:
        compiler.error(f'El tipo {symbol.name} no tiene cuerpo')
        return node

    fields: list[FieldSpec] = []
    seen: set[str] = set()
    expected = 'VAR_DECLARATION' if symbol.kind == 'flags' else 'VAR_INITIALIZATION'

    for declaration in _field_nodes(body):
        handle = handle_declaration(declaration)
        if handle is None or not handle.name:
            compiler.error(f'El tipo {symbol.name} contiene un campo invalido')
            continue
        if handle.name in seen:
            compiler.error(f'El campo {symbol.name}.{handle.name} ya fue declarado')
            continue
        seen.add(handle.name)

        if declaration.name != expected:
            compiler.error(
                f'El tipo {symbol.kind} {symbol.name} no permite inicializadores '
                f'en sus campos'
            )
            continue

        type_spec = _resolve_field_type(compiler, handle, symbol.name)
        if type_spec is None:
            continue

        value_info = None
        if symbol.kind == 'flags':
            value_info = _validate_flags_value(
                compiler, symbol.name, handle, type_spec
            )
            if value_info is None:
                continue
        fields.append(FieldSpec(handle.name, type_spec, value_info))

    symbol.fields = tuple(fields)
    return node


__all__ = ['collect', 'validate']

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from core.frontend.objects import EnumMember, EnumSymbol, TypeSpec
from core.frontend.tools.types import (
    INTEGER_TYPES,
    TypeResolutionError,
    _integer_bounds,
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


def _find_all(node: object, name: str) -> Iterable[gast.ASTRef]:
    if isinstance(node, gast.ASTRef):
        if node.name == name:
            yield node
        for child in node.nodes:
            yield from _find_all(child, name)
    elif isinstance(node, list):
        for child in node:
            yield from _find_all(child, name)


def _find_number(node: object) -> int | None:
    if type(node).__name__ == 'LiteralNumber':
        value = _token_value(node)
        return int(value) if value is not None else None
    for child in _children(node):
        found = _find_number(child)
        if found is not None:
            return found
    return None


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


def _base_type_node(node: gast.ASTRef) -> object | None:
    children = _children(node)
    found_name = False
    for child in children:
        if not found_name:
            if _token_kind(child) == 'IDENT':
                found_name = True
            continue
        if _token_value(child) == ':':
            break
        if isinstance(child, list) and child:
            return child
        if isinstance(child, gast.ASTRef):
            return child
    return None


def _resolve_base_type(compiler: Compiler, node: gast.ASTRef) -> TypeSpec:
    type_node = _base_type_node(node)
    if type_node is None:
        return TypeSpec('int32')

    try:
        type_spec = resolve_type(
            type_node,
            pointer_size=compiler.storage.pointer_size,
        )
    except TypeResolutionError as error:
        compiler.error(f'El tipo base del enum es invalido: {error}')
        return TypeSpec('int32')

    if (
        type_spec.name not in INTEGER_TYPES
        or type_spec.pointer_level
        or type_spec.array_depth
        or type_spec.value_is_const
    ):
        compiler.error(
            'El tipo base de un enum debe ser un entero escalar sin constancia'
        )
        return TypeSpec('int32')
    return type_spec


def collect(compiler: Compiler, nodes: list[gast.ASTRef]) -> None:
    """Register enum names before aggregate fields are resolved."""
    for node in nodes:
        if node.name != 'ENUM':
            continue
        name = _find_identifier(node)
        if not name:
            compiler.error('La declaracion enum no tiene nombre')
            continue
        symbol = EnumSymbol(
            name=name,
            base_type=_resolve_base_type(compiler, node),
            privacy=_privacy(node),
        )
        if not compiler.storage.define_type(symbol):
            compiler.error(f'El tipo ya fue declarado: {name}')
            continue
        compiler.type_bindings[id(node)] = symbol


def validate(compiler: Compiler, node: gast.ASTRef):
    symbol = compiler.type_bindings.get(id(node))
    if not isinstance(symbol, EnumSymbol):
        return node

    body = next(iter(_find_all(node, 'ENUM_BODY')), None)
    if body is None:
        compiler.error(f'El enum {symbol.name} no tiene cuerpo')
        return node

    members: list[EnumMember] = []
    seen: set[str] = set()
    next_value = 0
    bounds = _integer_bounds(symbol.base_type)
    for item in _find_all(body, 'ENUM_ITEM'):
        name = _find_identifier(item)
        if not name:
            compiler.error(f'El enum {symbol.name} contiene un miembro invalido')
            continue
        if name in seen:
            compiler.error(f'El miembro {symbol.name}.{name} ya fue declarado')
            continue
        seen.add(name)

        explicit = _find_number(item)
        if explicit is not None:
            next_value = int(explicit)
        if bounds is not None and not bounds[0] <= next_value <= bounds[1]:
            compiler.error(
                f'El valor de {symbol.name}.{name} esta fuera del rango de '
                f'{symbol.base_type.canonical_name}: {next_value}'
            )
        members.append(EnumMember(name, next_value))
        next_value += 1

    symbol.members = tuple(members)
    return node


__all__ = ['collect', 'validate']

from __future__ import annotations

from gram import ast as gast

from core.frontend.objects import OpaqueSymbol, TypeSpec
from core.frontend.tools.types import (
    INTEGER_TYPES,
    TypeResolutionError,
    _children,
    _token_kind,
    _token_value,
    resolve_type,
)


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


def _signature(node: object) -> gast.ASTRef | None:
    if isinstance(node, gast.ASTRef) and node.name == 'OPAQUE_SIGNATURE':
        return node
    for child in _children(node):
        found = _signature(child)
        if found is not None:
            return found
    return None


def _identifier(node: object) -> str | None:
    if _token_kind(node) == 'IDENT':
        return str(_token_value(node))
    for child in _children(node):
        found = _identifier(child)
        if found is not None:
            return found
    return None


def _representation_node(
    signature: gast.ASTRef,
) -> tuple[str | None, object | None, int]:
    children = _children(signature)
    name = None
    colon_index = None
    for index, child in enumerate(children):
        if _token_kind(child) == 'IDENT' and name is None:
            name = str(_token_value(child))
        if _token_kind(child) == 'COLON':
            colon_index = index
            break
    if colon_index is None or colon_index + 1 >= len(children):
        return name, None, 0
    type_node = children[colon_index + 1]
    pointer_level = sum(
        len(child.nodes)
        for child in children[colon_index + 2:]
        if isinstance(child, gast.ASTRef) and child.name == 'POINTER'
    )
    return name, type_node, pointer_level


def _validate_representation(
    compiler: object,
    name: str,
    type_node: object,
    pointer_level: int,
) -> TypeSpec:
    representation = resolve_type(
        type_node,
        pointer_level=pointer_level,
        pointer_size=compiler.storage.pointer_size,
    )
    if representation.value_is_const or representation.is_unique:
        raise TypeResolutionError(
            f'La representacion de opaque {name} no puede ser const ni unique'
        )
    if representation.array_depth:
        raise TypeResolutionError(
            f'La representacion de opaque {name} no puede ser un array'
        )
    if representation.pointer_level:
        if representation.name != 'void' or representation.pointer_level != 1:
            raise TypeResolutionError(
                f'La representacion de opaque {name} debe ser void* o un entero escalar'
            )
    elif representation.name not in INTEGER_TYPES:
        raise TypeResolutionError(
            f'La representacion de opaque {name} debe ser void* o un entero escalar'
        )
    return representation


def collect(compiler: object, nodes: list[gast.ASTRef]) -> None:
    """Register opaque names before signatures and externs are resolved."""
    for node in nodes:
        if node.name != 'OPAQUE':
            continue
        signature = _signature(node)
        if signature is None:
            compiler.error('La declaracion opaque no tiene una firma valida')
            continue
        name, type_node, pointer_level = _representation_node(signature)
        if not name or type_node is None:
            compiler.error('La declaracion opaque no tiene nombre o representacion')
            continue
        try:
            representation = _validate_representation(
                compiler,
                name,
                type_node,
                pointer_level,
            )
        except TypeResolutionError as error:
            compiler.error(str(error))
            continue
        symbol = OpaqueSymbol(
            name=name,
            representation=representation,
            privacy=_privacy(signature),
            module_path=compiler.module_for_node(node),
        )
        if not compiler.storage.define_type(symbol):
            compiler.error(f'El tipo ya fue declarado: {name}')


def resolve_opaque(storage: object, name: str) -> OpaqueSymbol | None:
    symbol = storage.resolve_type(name)
    if symbol is None:
        types = getattr(storage, 'types', {})
        symbol = types.get(name)
        if symbol is None:
            aliases = getattr(storage, 'type_aliases', {})
            target = aliases.get(name)
            if target is not None:
                symbol = types.get(target)
    return symbol if isinstance(symbol, OpaqueSymbol) else None


def is_opaque_type(storage: object, type_spec: TypeSpec) -> bool:
    return resolve_opaque(storage, type_spec.name) is not None


def validate_opaque_use(
    storage: object,
    type_spec: TypeSpec,
    context: str,
) -> None:
    if not is_opaque_type(storage, type_spec):
        return
    if type_spec.pointer_level or type_spec.array_depth:
        raise TypeResolutionError(
            f'{context} no puede envolver un tipo opaque con punteros ni arrays'
        )


__all__ = [
    'collect',
    'is_opaque_type',
    'resolve_opaque',
    'validate_opaque_use',
]

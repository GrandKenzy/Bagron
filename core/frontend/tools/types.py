from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from core.frontend.objects import TypeSpec, ValueInfo, Variable
from gram import ast as gast


INTEGER_WIDTHS = {
    'int8': 8,
    'int16': 16,
    'int32': 32,
    'int64': 64,
    'uint8': 8,
    'uint16': 16,
    'uint32': 32,
    'uint64': 64,
    'byte': 8,
}
SIGNED_INTEGER_TYPES = {'int', 'int8', 'int16', 'int32', 'int64', 'Bint'}
UNSIGNED_INTEGER_TYPES = {'uint', 'uint8', 'uint16', 'uint32', 'uint64', 'byte', 'uBint'}
INTEGER_TYPES = SIGNED_INTEGER_TYPES | UNSIGNED_INTEGER_TYPES


class TypeResolutionError(ValueError):
    pass


class ValueResolutionError(ValueError):
    pass


class UnsupportedExpressionError(ValueResolutionError):
    """Raised for expressions deferred to the expression-checking phase."""
    pass


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


def _token(node: object) -> object | None:
    return getattr(node, 'token', None)


def _token_value(node: object) -> Any:
    token = _token(node)
    return getattr(token, 'value', None)


def _token_kind(node: object) -> str | None:
    token = _token(node)
    token_type = getattr(token, 'token', token)
    return getattr(token_type, 'name', None)


def _resolve_symbol(
    namespace: Mapping[str, object] | Callable[[str], object | None],
    name: str,
) -> object | None:
    if callable(namespace):
        return namespace(name)
    return namespace.get(name)


def _type_name(node: object) -> str:
    if isinstance(node, list):
        return ''.join(_type_name(item) for item in node)

    if isinstance(node, gast.ASTRef):
        return _type_name(node.nodes)

    value = _token_value(node)
    if value is not None:
        return '' if value == 'const' else str(value)

    return str(getattr(node, 'value', ''))


def _type_is_const(node: object) -> bool:
    if isinstance(node, list):
        return any(_type_is_const(item) for item in node)
    if isinstance(node, gast.ASTRef):
        return _type_is_const(node.nodes)
    return _token_value(node) == 'const'


def resolve_type(
    type_node: object,
    *,
    pointer_level: int = 0,
    pointer_is_const: bool = False,
) -> TypeSpec:
    text = _type_name(type_node)
    array_depth = text.count('[]')
    base_name = text.replace('[]', '')
    bit_width = None
    signed = None

    match = re.fullmatch(r'(Bint|uBint)<(\d+)>', base_name)
    if match is not None:
        base_name = match.group(1)
        bit_width = int(match.group(2))
        signed = base_name == 'Bint'
        if bit_width < 1:
            raise TypeResolutionError(
                f'El ancho de {base_name} debe ser mayor que cero: {bit_width}'
            )

    return TypeSpec(
        name=base_name,
        bit_width=bit_width,
        signed=signed,
        pointer_level=pointer_level,
        array_depth=array_depth,
        value_is_const=_type_is_const(type_node),
        pointer_is_const=pointer_is_const,
    )


def _unwrap_value(node: object) -> object:
    current = node
    while (
        isinstance(current, gast.ASTRef)
        and current.name in ('VALUE', 'POSTFIX_EXPR', 'PRIMARY')
        and len(current.nodes) == 1
    ):
        current = current.nodes[0]
    return current


def infer_value(
    node: object,
    namespace: Mapping[str, object] | Callable[[str], object | None],
) -> ValueInfo:
    current = _unwrap_value(node)

    if isinstance(current, gast.ASTRef) and current.name == 'ARRAY_VALUE':
        array_node = next(iter(_children(current)), None)
        items = tuple(
            infer_value(item, namespace)
            for item in _children(array_node)
        )
        item_type = items[0].type_spec if items else TypeSpec('array')
        return ValueInfo(
            type_spec=TypeSpec(
                name=item_type.name,
                bit_width=item_type.bit_width,
                signed=item_type.signed,
                array_depth=item_type.array_depth + 1,
            ),
            is_literal=True,
            value=items,
            items=items,
        )

    if isinstance(current, gast.ASTRef):
        raise UnsupportedExpressionError(
            'solo se permiten literales, arrays literales o variables visibles en el scope'
        )

    kind = _token_kind(current)
    value = _token_value(current)

    if kind == 'IDENT':
        symbol = _resolve_symbol(namespace, str(value))
        if not isinstance(symbol, Variable) or symbol.type_spec is None:
            raise ValueResolutionError(f'La variable global no existe: {value}')
        return ValueInfo(
            type_spec=symbol.type_spec,
            identifier=str(value),
            value=symbol.value,
        )

    if kind == 'BOOL' or isinstance(value, bool):
        return ValueInfo(TypeSpec('bool'), is_literal=True, value=value)

    if kind == 'STRING':
        return ValueInfo(TypeSpec('chain'), is_literal=True, value=value)

    if kind == 'NULL':
        return ValueInfo(TypeSpec('Null'), is_literal=True, value=value)

    if kind == 'NUMBER':
        number_type = 'float' if isinstance(value, float) else 'int'
        return ValueInfo(TypeSpec(number_type), is_literal=True, value=value)

    raise UnsupportedExpressionError('el inicializador no es un literal compatible')


def _integer_bounds(type_spec: TypeSpec) -> tuple[int, int] | None:
    if type_spec.name == 'Bint' and type_spec.bit_width is not None:
        if type_spec.signed:
            return -(2 ** (type_spec.bit_width - 1)), 2 ** (type_spec.bit_width - 1) - 1
        return 0, 2 ** type_spec.bit_width - 1

    width = INTEGER_WIDTHS.get(type_spec.name)
    if width is None:
        if type_spec.name == 'int':
            width = 32
        elif type_spec.name in ('uint', 'wsize'):
            width = 32
        elif type_spec.name == 'uBint' and type_spec.bit_width is not None:
            width = type_spec.bit_width
        else:
            return None

    if type_spec.name in SIGNED_INTEGER_TYPES:
        return -(2 ** (width - 1)), 2 ** (width - 1) - 1
    return 0, 2 ** width - 1


def _same_shape(left: TypeSpec, right: TypeSpec) -> bool:
    return (
        left.name == right.name
        and left.bit_width == right.bit_width
        and left.signed == right.signed
        and left.pointer_level == right.pointer_level
        and left.array_depth == right.array_depth
        and (
            left.pointer_level == 0
            or left.value_is_const == right.value_is_const
        )
    )


def is_compatible(target: TypeSpec, source: ValueInfo) -> bool:
    source_type = source.type_spec

    if source_type.name == 'Null':
        return target.pointer_level > 0 and target.array_depth == 0

    if target.pointer_level > 0 and source.is_literal:
        return False

    if target.array_depth > 0:
        if source_type.array_depth != target.array_depth:
            return source_type.array_depth == target.array_depth and not source.is_literal
        if source.is_literal and not source.items:
            return True
        if not source.items:
            return True
        element_target = TypeSpec(
            name=target.name,
            bit_width=target.bit_width,
            signed=target.signed,
            pointer_level=target.pointer_level,
            array_depth=target.array_depth - 1,
            value_is_const=target.value_is_const,
        )
        return all(is_compatible(element_target, item) for item in source.items)

    if source_type.array_depth > 0:
        return False

    if source.is_literal and source_type.name == 'int' and target.name in INTEGER_TYPES:
        if not isinstance(source.value, int) or isinstance(source.value, bool):
            return False
        bounds = _integer_bounds(target)
        return bounds is not None and bounds[0] <= source.value <= bounds[1]

    if source.is_literal and source_type.name in ('int', 'float'):
        if target.name in ('middle', 'float', 'double'):
            return True

    return _same_shape(target, source_type)

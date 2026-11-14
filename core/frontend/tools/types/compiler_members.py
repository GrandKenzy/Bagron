"""Semantic resolution for read-only ``.<...>`` compiler members."""

from __future__ import annotations

from core.frontend.objects import (
    AggregateSymbol,
    DefinedIntegerSymbol,
    EnumSymbol,
    TypeSpec,
    ValueInfo,
)

from .common import FLOAT_TYPES, INTEGER_WIDTHS, ValueResolutionError
from .resolution import _identifier_from_node, _namespace_owner, is_buffer_type


def _usize(namespace: object) -> TypeSpec:
    owner = _namespace_owner(namespace)
    return TypeSpec(
        'usize',
        bit_width=getattr(owner, 'pointer_size', 8) * 8,
        signed=False,
        value_is_const=True,
    )


def _scalar_size(type_spec: TypeSpec, namespace: object) -> int | None:
    owner = _namespace_owner(namespace)
    pointer_size = getattr(owner, 'pointer_size', 8)
    if type_spec.pointer_level:
        return pointer_size
    if type_spec.name in {'chain', 'buffer', 'void', 'Never'}:
        return None
    width = type_spec.bit_width or INTEGER_WIDTHS.get(type_spec.name)
    if type_spec.name in FLOAT_TYPES:
        width = {'middle': 16, 'float': 32, 'double': 64}[type_spec.name]
    resolver = getattr(owner, 'resolve_type', None)
    symbol = resolver(type_spec.name) if callable(resolver) else None
    if isinstance(symbol, DefinedIntegerSymbol):
        width = symbol.bit_width
    elif isinstance(symbol, EnumSymbol):
        width = symbol.base_type.bit_width or INTEGER_WIDTHS.get(
            symbol.base_type.name
        )
    elif isinstance(symbol, AggregateSymbol):
        return None
    if width is None:
        return None
    return max(1, (int(width) + 7) // 8)


def _array_element_size(type_spec: TypeSpec, namespace: object) -> int | None:
    scalar = _scalar_size(
        TypeSpec(
            type_spec.name,
            bit_width=type_spec.bit_width,
            signed=type_spec.signed,
            pointer_level=type_spec.pointer_level,
            nominal_key=type_spec.nominal_key,
        ),
        namespace,
    )
    if scalar is None:
        return None
    dimensions = type_spec.array_lengths[1:]
    if any(length is None for length in dimensions):
        return None
    size = scalar
    for length in dimensions:
        size *= int(length)
    return size


def compiler_member_value(
    value: ValueInfo,
    suffix: object,
    namespace: object,
    *,
    current_function: object | None = None,
) -> ValueInfo:
    """Resolve a compiler member without exposing mutable storage."""

    member = _identifier_from_node(suffix)
    if member not in {'len', 'size', 'region'}:
        raise ValueResolutionError(
            f'El miembro del compilador <{member or "anonimo"}> no existe'
        )
    type_spec = value.type_spec
    result_type = _usize(namespace)
    literal = False
    result: object = None

    if member == 'len':
        if type_spec.pointer_level:
            raise ValueResolutionError('.<len> no aplica a punteros crudos')
        if type_spec.array_depth:
            result = type_spec.array_lengths[0] if type_spec.array_lengths else None
            literal = result is not None
        elif is_buffer_type(type_spec):
            result = type_spec.array_lengths[0] if type_spec.array_lengths else None
            literal = result is not None
        elif type_spec.name == 'chain':
            if value.is_literal and isinstance(value.value, str):
                result = len(value.value.encode('utf-8')) + 1
                literal = True
        else:
            raise ValueResolutionError(
                '.<len> solo aplica a arrays, buffer y chain'
            )
    elif member == 'size':
        if type_spec.name in {'chain', 'buffer'} and not type_spec.pointer_level:
            raise ValueResolutionError('.<size> no aplica a chain ni buffer')
        result = (
            _array_element_size(type_spec, namespace)
            if type_spec.array_depth
            else _scalar_size(type_spec, namespace)
        )
        literal = result is not None
    else:
        if value.region_origin is None:
            raise ValueResolutionError(
                '.<region> requiere almacenamiento de procedencia conocida'
            )
        result_type = TypeSpec('__region', value_is_const=True)
        result = value.region_origin
        literal = True

    resolved = ValueInfo(
        result_type,
        is_literal=literal,
        value=result,
        compiler_member=member,
        compiler_member_source=value,
    )
    if current_function is not None:
        current_function.compiler_members[id(suffix)] = resolved
    return resolved


__all__ = ['compiler_member_value']

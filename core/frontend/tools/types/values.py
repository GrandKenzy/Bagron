from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from core.frontend.objects import AggregateSymbol, TypeSpec, ValueInfo, Variable
from gram import ast as gast

from .common import (
    BITWISE_OPERATORS, COMPARISON_OPERATORS, INTEGER_TYPES,
    LOGICAL_NOT_OPERATORS, LOGICAL_OPERATORS, MAGIC_BINARY_OPERATORS,
    MAGIC_UNARY_OPERATORS, UnsupportedExpressionError, ValueResolutionError,
    _children, _token_kind, _token_value,
)
from .resolution import (
    _float_rank, _identifier_from_node, _namespace_owner,
    _require_known_pointer, _resolve_aggregate, _resolve_symbol,
    buffer_capacity, is_buffer_type, is_condition_type, _is_float_scalar,
)
from .compatibility import _integer_common_type
from .postfix import (
    _address_type, _deref_value, _infer_postfix, _unwrap_value,
)
from .calls import _infer_magic_operator


def _member_value(
    value: ValueInfo,
    suffix: object,
    namespace: Mapping[str, object] | Callable[[str], object | None],
    *,
    current_function: object | None = None,
) -> ValueInfo:
    member = _identifier_from_node(suffix)
    if (
        member == 'len'
        and value.type_spec.pointer_level == 0
        and value.type_spec.array_depth == 1
    ):
        length = (
            value.type_spec.array_lengths[0]
            if value.type_spec.array_lengths
            else None
        )
        pointer_size = getattr(_namespace_owner(namespace), 'pointer_size', 8)
        return ValueInfo(
            TypeSpec(
                'usize',
                bit_width=pointer_size * 8,
                signed=False,
            ),
            is_literal=length is not None,
            value=length,
        )
    if value.type_spec.pointer_level or value.type_spec.array_depth:
        raise ValueResolutionError(
            'el acceso a miembros requiere un struct o mold ya desreferenciado'
        )
    if value.is_lvalue:
        _require_known_pointer(value, current_function, 'el acceso al miembro')
    aggregate = _resolve_aggregate(namespace, value.type_spec.name)
    if aggregate is None:
        raise ValueResolutionError(
            f'El tipo {value.type_spec.canonical_name} no tiene miembros'
        )
    owner = _namespace_owner(namespace)
    resolver = getattr(owner, 'resolve_field', None)
    field = (
        resolver(value.type_spec.name, member)
        if callable(resolver)
        else next((field for field in aggregate.fields if field.name == member), None)
    )
    if field is None:
        raise ValueResolutionError(
            f'El miembro {member or "<anonimo>"} no existe en {aggregate.name}'
        )
    return ValueInfo(
        type_spec=field.type_spec,
        is_lvalue=True,
        identifier=value.identifier,
        # A pointer read through a raw union member has no safe provenance.
        # Taking the member's address still uses ``storage_origin`` below.
        address_origin=(
            'unknown'
            if aggregate.kind == 'mold' and field.type_spec.pointer_level
            else value.address_origin
        ),
        storage_origin=value.storage_origin or value.address_origin,
        address_path=(*value.address_path, ('member', member)),
        is_addressable=aggregate.kind != 'flags',
        pointer_provenance_unknown=(
            aggregate.kind == 'mold' and field.type_spec.pointer_level > 0
        ),
        member_owner=aggregate.name,
        region_origin=value.region_origin,
    )


def _infer_deref_target(
    node: object,
    namespace: Mapping[str, object] | Callable[[str], object | None],
    functions: Mapping[str, object] | Callable[[str], object | None] | None,
    current_function: object | None = None,
) -> ValueInfo:
    children = _children(node)
    inner = children[0] if children else None
    if inner is None:
        raise ValueResolutionError('La desreferenciacion esta vacia')
    if _token_kind(inner) == 'IDENT':
        value = infer_value(
            inner,
            namespace,
            functions,
            current_function=current_function,
        )
        _require_known_pointer(value, current_function, 'la desreferenciacion')
        return _deref_value(value)
    value = _infer_deref_target(
        inner,
        namespace,
        functions,
        current_function=current_function,
    )
    _require_known_pointer(value, current_function, 'la desreferenciacion')
    return _deref_value(value)


def infer_lvalue(
    node: object,
    namespace: Mapping[str, object] | Callable[[str], object | None],
    functions: Mapping[str, object] | Callable[[str], object | None] | None = None,
    *,
    current_function: object | None = None,
) -> ValueInfo:
    """Resolve an assignment target and require addressable storage."""
    current = node
    if isinstance(current, gast.ASTRef) and current.name == 'ASSIGN_TARGET':
        children = _children(current)
        current = children[0] if children else current

    name = getattr(current, 'name', None)
    if name in {'DEREF_TARGET', 'DEREF_ASSIGN_TARGET'}:
        result = _infer_deref_target(
            current,
            namespace,
            functions,
            current_function=current_function,
        )
    else:
        result = infer_value(
            current,
            namespace,
            functions,
            current_function=current_function,
        )
    if not result.is_lvalue:
        raise ValueResolutionError('el destino no es direccionable')
    return result


from .value_inference import infer_value

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from core.frontend.objects import AggregateSymbol, TypeSpec, ValueInfo, Variable
from gram import ast as gast

from .common import (
    INTEGER_TYPES, INTEGER_WIDTHS, SIGNED_INTEGER_TYPES,
    UNSIGNED_INTEGER_TYPES, TypeResolutionError, ValueResolutionError,
)
from .resolution import buffer_capacity, is_buffer_type


def _constant_char_bytes(value: ValueInfo) -> bytes | None:
    """Return compile-time bytes from a constant char or char array."""
    if not value.is_literal:
        return None

    type_spec = value.type_spec
    if type_spec.name == 'chain' and type_spec.array_depth == 0:
        return _string_bytes(value.value)

    if (
        type_spec.name == 'char'
        and type_spec.pointer_level == 0
        and type_spec.array_depth == 0
    ):
        if isinstance(value.value, str):
            data = _string_bytes(value.value, ascii_only=True)
            return data if data is not None and len(data) == 1 else None
        if isinstance(value.value, int) and 0 <= value.value <= 255:
            return bytes((value.value,))
        return None

    if (
        type_spec.name != 'char'
        or type_spec.pointer_level
        or type_spec.array_depth != 1
    ):
        return None

    if isinstance(value.value, str):
        return _string_bytes(value.value, ascii_only=True)

    if not value.items:
        return None

    result = bytearray()
    for item in value.items:
        if item.type_spec.name == 'chain' and item.is_literal:
            data = _string_bytes(item.value, ascii_only=True)
            if data is None or len(data) != 1:
                return None
            result.extend(data)
            continue
        if (
            item.type_spec.name == 'char'
            and item.is_literal
            and isinstance(item.value, int)
            and 0 <= item.value <= 255
        ):
            result.append(item.value)
            continue
        return None
    return bytes(result)


def constant_chain_value(value: ValueInfo) -> ValueInfo | None:
    """Convert a compile-time char value into the chain semantic value."""
    data = _constant_char_bytes(value)
    if data is None:
        return None
    try:
        text = data.decode('ascii')
    except UnicodeDecodeError as error:
        raise ValueResolutionError('Una conversion a chain solo acepta ASCII') from error
    return ValueInfo(TypeSpec('chain'), is_literal=True, value=text)


def _is_integer_scalar(type_spec: TypeSpec) -> bool:
    return (
        type_spec.pointer_level == 0
        and type_spec.array_depth == 0
        and type_spec.name in INTEGER_TYPES
    )


def _integer_bounds(type_spec: TypeSpec) -> tuple[int, int] | None:
    if type_spec.name == 'Bint' and type_spec.bit_width is not None:
        if type_spec.signed:
            return -(2 ** (type_spec.bit_width - 1)), 2 ** (type_spec.bit_width - 1) - 1
        return 0, 2 ** type_spec.bit_width - 1

    width = INTEGER_WIDTHS.get(type_spec.name)
    if width is None:
        if type_spec.name in {'uBint', 'usize', 'isize'} and type_spec.bit_width is not None:
            width = type_spec.bit_width
        else:
            return None

    if type_spec.name in SIGNED_INTEGER_TYPES:
        return -(2 ** (width - 1)), 2 ** (width - 1) - 1
    return 0, 2 ** width - 1


def _string_bytes(value: object, *, ascii_only: bool = False) -> bytes | None:
    if not isinstance(value, str):
        return None
    try:
        return value.encode('ascii' if ascii_only else 'utf-8')
    except UnicodeEncodeError:
        return None


def _target_array_length(type_spec: TypeSpec, dimension: int) -> int | None:
    if not type_spec.array_lengths:
        return None
    return type_spec.array_lengths[dimension]


def _literal_array_shape(value: ValueInfo) -> tuple[int, ...] | None:
    """Return a rectangular shape for an array literal, if it has one."""
    if value.type_spec.array_depth == 0:
        return ()
    if not value.items:
        return (0,)

    child_shapes = [
        _literal_array_shape(item)
        for item in value.items
    ]
    if any(shape is None for shape in child_shapes):
        return None
    first_shape = child_shapes[0]
    if any(shape != first_shape for shape in child_shapes[1:]):
        return None
    return (len(value.items), *first_shape)


def _same_shape(left: TypeSpec, right: TypeSpec) -> bool:
    return (
        left.name == right.name
        and left.bit_width == right.bit_width
        and left.signed == right.signed
        and left.pointer_level == right.pointer_level
        and left.array_depth == right.array_depth
        and left.array_lengths == right.array_lengths
        and not (
            left.pointer_level > 0
            and right.value_is_const
            and not left.value_is_const
        )
    )


def _integer_width(type_spec: TypeSpec) -> int | None:
    if type_spec.name in {'Bint', 'uBint', 'usize', 'isize'}:
        return type_spec.bit_width
    return INTEGER_WIDTHS.get(type_spec.name)


def target_iteration_limit(pointer_size: int) -> int:
    """Return the signed index/range ceiling for the selected target."""
    if pointer_size not in {4, 8}:
        raise TypeResolutionError(
            f'El tamano de puntero del target no es valido: {pointer_size} bytes'
        )
    return (1 << (pointer_size * 8 - 1)) - 1


def is_compatible(target: TypeSpec, source: ValueInfo) -> bool:
    source_type = source.type_spec

    if target.name == 'Never' or source_type.name == 'Never':
        return False

    if source_type.name == 'Null':
        return target.pointer_level > 0 and target.array_depth == 0

    if is_buffer_type(target):
        target_capacity = buffer_capacity(target)
        if is_buffer_type(source_type):
            source_capacity = buffer_capacity(source_type)
            return (
                target_capacity is None
                or (
                    source_capacity is not None
                    and source_capacity == target_capacity
                )
            )
        if (
            source.is_literal
            and source_type.pointer_level == 0
            and source_type.array_depth == 0
            and source_type.name in INTEGER_TYPES
        ):
            return source.value == 0 and target_capacity is not None
        if (
            source.is_literal
            and source_type.pointer_level == 0
            and source_type.array_depth == 1
            and source.items
        ):
            if target_capacity is not None and len(source.items) > target_capacity:
                return False
            return all(
                is_compatible(TypeSpec('byte'), item)
                for item in source.items
            )
        return False

    if (
        target.name == 'void'
        and source_type.name == 'void'
        and target.pointer_level == 0
        and source_type.pointer_level == 0
    ):
        return False

    if (
        target.pointer_level == 1
        and source_type.pointer_level == 1
        and target.array_depth == 0
        and source_type.array_depth == 0
        and (target.name == 'void' or source_type.name == 'void')
    ):
        if source_type.value_is_const and not target.value_is_const:
            return False
        return target.pointer_is_const == source_type.pointer_is_const

    if (
        source.is_literal
        and source_type.name == 'chain'
        and target.pointer_level == 1
        and target.array_depth == 0
        and target.name in {'char', 'byte'}
        and target.value_is_const
    ):
        data = _string_bytes(
            source.value,
            ascii_only=target.name == 'char',
        )
        return data is not None

    if target.pointer_level > 0 and source.is_literal:
        return False

    if target.array_depth > 0:
        if source_type.value_is_const and not target.value_is_const:
            return False

        if target.array_depth > 1 and source.is_literal:
            literal_shape = _literal_array_shape(source)
            if (
                literal_shape is None
                or len(literal_shape) != target.array_depth
            ):
                return False
            for dimension, target_length in enumerate(target.array_lengths):
                if (
                    target_length is not None
                    and literal_shape[dimension] != target_length
                ):
                    return False
        if (
            target.array_depth == 1
            and source.is_literal
            and source_type.name == 'chain'
            and source_type.array_depth == 0
            and target.name in {'char', 'byte'}
        ):
            data = _string_bytes(source.value, ascii_only=target.name == 'char')
            if data is None:
                return False
            declared_length = _target_array_length(target, 0)
            required_length = len(data) + (1 if target.name == 'char' else 0)
            return declared_length is None or required_length <= declared_length

        if (
            target.array_depth == 1
            and target.name == 'char'
            and source.is_literal
            and source_type.array_depth == 1
        ):
            declared_length = _target_array_length(target, 0)
            source_length = (
                source_type.array_lengths[0]
                if source_type.array_lengths
                else None
            )
            if (
                declared_length is not None
                and source_length is not None
                and source_length + 1 > declared_length
            ):
                return False

        if source_type.array_depth != target.array_depth:
            return False

        for dimension in range(target.array_depth):
            target_length = _target_array_length(target, dimension)
            source_length = (
                source_type.array_lengths[dimension]
                if dimension < len(source_type.array_lengths)
                else None
            )
            if target_length is None:
                continue
            if source.is_literal:
                if target.array_depth > 1:
                    if source_length is None or source_length != target_length:
                        return False
                elif source_length is not None and source_length > target_length:
                    return False
            elif source_length is None or source_length != target_length:
                return False

        if source.is_literal and not source.items:
            if any(
                length is None
                for length in target.array_lengths
            ):
                return False
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
            array_lengths=target.array_lengths[1:] if target.array_lengths else (),
        )
        return all(is_compatible(element_target, item) for item in source.items)

    if target.name == 'chain':
        if source_type.name == 'chain' and source_type.array_depth == 0:
            return True
        return _constant_char_bytes(source) is not None

    if source_type.array_depth > 0:
        return False

    if source.is_literal and source_type.name == 'chain' and target.name in {
        'char',
        'byte',
    }:
        data = _string_bytes(source.value, ascii_only=target.name == 'char')
        return data is not None and len(data) == 1

    if source.is_literal and source_type.name == 'int32' and target.name in INTEGER_TYPES:
        if not isinstance(source.value, int) or isinstance(source.value, bool):
            return False
        bounds = _integer_bounds(target)
        return bounds is not None and bounds[0] <= source.value <= bounds[1]

    if source.is_literal and source_type.name in ('int32', 'float'):
        if target.name in ('middle', 'float', 'double'):
            return True

    if (
        target.pointer_level == 0
        and source_type.pointer_level == 0
        and target.array_depth == 0
        and source_type.array_depth == 0
        and target.name in INTEGER_TYPES
        and source_type.name in INTEGER_TYPES
    ):
        target_width = _integer_width(target)
        source_width = _integer_width(source_type)
        if target_width is None or source_width is None:
            return False
        if _same_shape(target, source_type):
            return True
        if target.name == 'byte' or source_type.name == 'byte':
            return False
        same_sign = (
            target.name in SIGNED_INTEGER_TYPES
            and source_type.name in SIGNED_INTEGER_TYPES
        ) or (
            target.name in UNSIGNED_INTEGER_TYPES
            and source_type.name in UNSIGNED_INTEGER_TYPES
        )
        return same_sign and target_width > source_width

    return _same_shape(target, source_type)


def _integer_common_type(left: ValueInfo, right: ValueInfo) -> TypeSpec | None:
    """Find a safe integer type for an operation without hidden narrowing."""
    left_type = left.type_spec
    right_type = right.type_spec
    if not _is_integer_scalar(left_type) or not _is_integer_scalar(right_type):
        return None
    if _same_shape(left_type, right_type):
        return left_type

    if left.is_literal and is_compatible(right_type, left):
        return right_type
    if right.is_literal and is_compatible(left_type, right):
        return left_type

    if left_type.name == 'byte' or right_type.name == 'byte':
        return None

    left_width = _integer_width(left_type)
    right_width = _integer_width(right_type)
    if left_width is None or right_width is None:
        return None
    left_signed = left_type.name in SIGNED_INTEGER_TYPES
    right_signed = right_type.name in SIGNED_INTEGER_TYPES
    if left_signed != right_signed:
        return None
    if left_width > right_width:
        return left_type
    if right_width > left_width:
        return right_type
    return None

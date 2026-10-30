from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from core.frontend.objects import AggregateSymbol, TypeSpec, ValueInfo, Variable
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
SIGNED_INTEGER_TYPES = {
    'int8', 'int16', 'int32', 'int64', 'isize', 'Bint',
}
UNSIGNED_INTEGER_TYPES = {
    'uint8', 'uint16', 'uint32', 'uint64', 'usize', 'byte', 'uBint',
}
INTEGER_TYPES = SIGNED_INTEGER_TYPES | UNSIGNED_INTEGER_TYPES
FOR_ITERATOR_TYPES = {'uint8', 'uint16', 'uint32', 'uint64'}
FLOAT_TYPES = {'middle', 'float', 'double'}
COMPARISON_OPERATORS = {
    'EQUAL',
    'NOT_EQUAL',
    'LESS',
    'LESS_EQUAL',
    'GREATER',
    'GREATER_EQUAL',
}
LOGICAL_OPERATORS = {
    'AND_LOGIC',
    'LOGIC_AND',
    'OR_LOGIC',
    'LOGIC_OR',
}
LOGICAL_NOT_OPERATORS = {'NOT_LOGIC', 'LOGIC_NOT', 'EXCLAMATION'}
BITWISE_OPERATORS = {'AND', 'OR', 'XOR', 'SHL', 'SHR'}
MAGIC_BINARY_OPERATORS = {
    'PLUS': ('__add__',),
    'MINUS': ('__sub__',),
    'STAR': ('__mul__',),
    'SLASH': ('__div__', '__truediv__'),
    'PERCENT': ('__mod__',),
    'AND': ('__and__',),
    'OR': ('__or__',),
    'XOR': ('__xor__',),
    'SHL': ('__shl__',),
    'SHR': ('__shr__',),
}
MAGIC_UNARY_OPERATORS = {
    'PLUS': ('__pos__',),
    'MINUS': ('__neg__',),
}


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

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from core.frontend.objects import AggregateSymbol, TypeSpec, ValueInfo, Variable
from gram import ast as gast

from .common import (
    BITWISE_OPERATORS, COMPARISON_OPERATORS, FLOAT_TYPES, FOR_ITERATOR_TYPES,
    INTEGER_TYPES, INTEGER_WIDTHS, LOGICAL_NOT_OPERATORS, LOGICAL_OPERATORS,
    MAGIC_BINARY_OPERATORS, MAGIC_UNARY_OPERATORS, SIGNED_INTEGER_TYPES,
    UNSIGNED_INTEGER_TYPES, TypeResolutionError, UnsupportedExpressionError,
    ValueResolutionError, _children, _token, _token_kind, _token_value,
)


def _resolve_symbol(
    namespace: Mapping[str, object] | Callable[[str], object | None],
    name: str,
) -> object | None:
    if callable(namespace):
        return namespace(name)
    return namespace.get(name)


def _resolve_function(
    functions: Mapping[str, object] | Callable[[str], object | None] | None,
    name: str,
    current_function: object | None = None,
) -> object | None:
    if functions is None:
        return None
    resolver = getattr(functions, 'resolve_for', None)
    if callable(resolver):
        function = resolver(name, current_function)
    else:
        function = _resolve_symbol(functions, name)
    if function is None:
        return None
    if getattr(function, 'privacy', 'public') != 'private':
        return function
    origin = getattr(function, 'module_path', None)
    active = getattr(current_function, 'module_path', None)
    if active is None:
        active = getattr(
            getattr(functions, 'storage', None),
            'active_module_path',
            None,
        )
    return function if origin is None or origin == active else None


def _unsafe_context(function: object | None) -> bool:
    return bool(getattr(function, 'is_unsafe', False))


def _require_known_pointer(
    value: ValueInfo,
    function: object | None,
    operation: str,
) -> None:
    if _unsafe_context(function):
        return
    if value.address_origin == 'unknown':
        raise ValueResolutionError(
            f'{operation} requiere un puntero de procedencia conocida; '
            'marca la funcion como @unsafe'
        )


def _validate_array_index(
    value: ValueInfo,
    index: ValueInfo,
    function: object | None,
) -> None:
    if _unsafe_context(function):
        return
    if not index.is_literal or not isinstance(index.value, int):
        length = (
            value.type_spec.array_lengths[0]
            if value.type_spec.array_lengths
            else None
        )
        proven_same_array = (
            index.known_index_source is not None
            and index.known_index_source == value.identifier
            and index.known_index_path == value.address_path
            and index.known_index_length is not None
            and index.known_index_length == length
        )
        if proven_same_array:
            return
        raise ValueResolutionError(
            'una funcion segura solo puede indexar arrays con un indice '
            'conocido en compilacion; usa @unsafe para un indice dinamico'
        )

    length = (
        value.type_spec.array_lengths[0]
        if value.type_spec.array_lengths
        else None
    )
    if length is None:
        raise ValueResolutionError(
            'el tamano del array no puede demostrarse en compilacion; '
            'usa @unsafe para indexarlo'
        )
    if index.value < 0 or index.value >= length:
        raise ValueResolutionError(
            f'el indice {index.value} esta fuera del rango del array [0, {length})'
        )


def _validate_chain_index(value: ValueInfo, index: ValueInfo) -> None:
    """Validate the statically provable range of a chain index.

    A chain parameter has no compile-time length in its signature, so dynamic
    and literal accesses to it retain the existing ``@unsafe`` requirement.
    Locally known literals, however, include their NUL byte in the only valid
    static range and must reject an obvious out-of-bounds index even in unsafe
    code.
    """
    if not index.is_literal or not isinstance(index.value, int):
        return
    if not value.is_literal or not isinstance(value.value, str):
        return
    try:
        length = len(value.value.encode('ascii')) + 1
    except UnicodeEncodeError as error:
        raise ValueResolutionError(
            'Una cadena usada por la ABI actual solo puede contener ASCII'
        ) from error
    if index.value < 0 or index.value >= length:
        raise ValueResolutionError(
            f'el indice {index.value} esta fuera del rango del chain [0, {length})'
        )


def _validate_buffer_index(value: ValueInfo, index: ValueInfo) -> None:
    """Validate the statically provable part of a buffer access.

    Dynamic indices remain legal for buffers because the LLVM backend carries
    the runtime capacity in the buffer descriptor and emits the bounds check.
    Literal indices are rejected here so an obvious mistake is still a
    compile-time diagnostic.
    """
    capacity = buffer_capacity(value.type_spec)
    if (
        index.is_literal
        and isinstance(index.value, int)
        and capacity is not None
        and (index.value < 0 or index.value >= capacity)
    ):
        raise ValueResolutionError(
            f'el indice {index.value} esta fuera del rango del buffer '
            f'[0, {capacity})'
        )


def _buffer_index_value(value: ValueInfo, index: ValueInfo) -> ValueInfo:
    _validate_buffer_index(value, index)
    return ValueInfo(
        TypeSpec(
            'byte',
            value_is_const=value.type_spec.value_is_const,
        ),
        is_lvalue=True,
        address_origin=value.address_origin,
        storage_origin=value.storage_origin or value.address_origin,
        identifier=value.identifier,
        address_path=(*value.address_path, ('index', index)),
        member_owner=value.member_owner,
        region_origin=value.region_origin,
    )


def _type_name(node: object) -> str:
    if isinstance(node, list):
        return ''.join(_type_name(item) for item in node)

    if isinstance(node, gast.ASTRef):
        return _type_name(node.nodes)

    value = _token_value(node)
    if value is not None:
        return '' if value in {'const', 'unique'} else str(value)

    return str(getattr(node, 'value', ''))


def _type_is_const(node: object) -> bool:
    if isinstance(node, list):
        return any(_type_is_const(item) for item in node)
    if isinstance(node, gast.ASTRef):
        return _type_is_const(node.nodes)
    return _token_value(node) == 'const'


def _type_is_unique(node: object) -> bool:
    """Return whether a parsed type carries the parameter-only unique flag."""
    if isinstance(node, list):
        return any(_type_is_unique(item) for item in node)
    if isinstance(node, gast.ASTRef):
        return _type_is_unique(node.nodes)
    return _token_value(node) == 'unique'


def _is_array_suffix_node(node: object) -> bool:
    """Return whether a type AST node is one ``[expression]`` suffix."""
    if not isinstance(node, list) or len(node) < 2:
        return False
    return (
        _token_kind(node[0]) == 'LBRACKET'
        and _token_kind(node[-1]) == 'RBRACKET'
    )


def _type_base_and_suffixes(type_node: object) -> tuple[str, list[object]]:
    """Extract the base name and dimension nodes from a parsed type.

    The grammar keeps a dimension expression as an AST value instead of
    flattening it into text.  This is important for ``buffer[8 * 100]``:
    the capacity must be evaluated as a constant expression, not guessed from
    the token spelling.
    """
    base: list[str] = []
    suffixes: list[object] = []

    def visit(node: object) -> None:
        if _is_array_suffix_node(node):
            suffixes.append(node)
            return
        if isinstance(node, list):
            for child in node:
                visit(child)
            return
        if isinstance(node, gast.ASTRef):
            if node.name == 'BITINT_TYPE':
                base.append(_type_name(node))
                return
            for child in _children(node):
                visit(child)
            return
        value = _token_value(node)
        if value is None or value in {'const', 'unique'}:
            return
        token_kind = _token_kind(node)
        if token_kind not in {'LBRACKET', 'RBRACKET'}:
            base.append(str(value))

    visit(type_node)
    return ''.join(base), suffixes


def _constant_dimension_value(suffix: object) -> int | None:
    """Resolve one type dimension, returning ``None`` for ``[]``."""
    from .values import infer_value

    expression = next(
        (
            child for child in suffix
            if _token_kind(child) not in {'LBRACKET', 'RBRACKET'}
        ),
        None,
    )
    if expression is None:
        return None
    try:
        value = infer_value(expression, {}, {}, current_function=None)
    except (UnsupportedExpressionError, ValueResolutionError) as error:
        raise TypeResolutionError(
            'el tamano de un array debe ser una expresion entera constante'
        ) from error
    if (
        not value.is_literal
        or value.type_spec.pointer_level
        or value.type_spec.array_depth
        or value.type_spec.name not in INTEGER_TYPES
        or not isinstance(value.value, int)
    ):
        raise TypeResolutionError(
            'el tamano de un array debe ser una expresion entera constante'
        )
    return int(value.value)


def is_buffer_type(type_spec: TypeSpec) -> bool:
    """Return whether a type spec describes a raw dynamic byte buffer."""
    return (
        type_spec.name == 'buffer'
        and type_spec.pointer_level == 0
        and type_spec.array_depth == 0
        and len(type_spec.array_lengths) == 1
    )


def buffer_capacity(type_spec: TypeSpec) -> int | None:
    """Return the compile-time capacity of a buffer, if it is known."""
    if not is_buffer_type(type_spec):
        return None
    return type_spec.array_lengths[0]


def _identifier_from_node(node: object) -> str | None:
    if _token_kind(node) == 'IDENT':
        return str(_token_value(node))
    for child in _children(node):
        found = _identifier_from_node(child)
        if found is not None:
            return found
    return None


def is_bool_scalar(type_spec: TypeSpec) -> bool:
    """Return whether a value is exactly a scalar ``bool``."""
    return (
        type_spec.name == 'bool'
        and type_spec.pointer_level == 0
        and type_spec.array_depth == 0
    )


def is_condition_type(type_spec: TypeSpec) -> bool:
    """Return whether a value can be used as a control-flow condition."""
    return is_bool_scalar(type_spec)


def _is_float_scalar(type_spec: TypeSpec) -> bool:
    return (
        type_spec.pointer_level == 0
        and type_spec.array_depth == 0
        and type_spec.name in FLOAT_TYPES
    )


def _float_rank(type_spec: TypeSpec) -> int:
    return {'middle': 16, 'float': 32, 'double': 64}[type_spec.name]


def resolve_type(
    type_node: object,
    *,
    pointer_level: int = 0,
    pointer_is_const: bool = False,
    pointer_size: int = 8,
    allow_bit_types: bool = False,
    allow_unique: bool = False,
) -> TypeSpec:
    base_name, suffixes = _type_base_and_suffixes(type_node)
    text = _type_name(type_node)
    unique = _type_is_unique(type_node)
    if unique and not allow_unique:
        raise TypeResolutionError(
            'unique solo puede usarse en parametros de funcion'
        )
    if not base_name:
        raise TypeResolutionError(f'Tipo invalido: {text or "<vacio>"}')

    if base_name in {'Len_t', 'Size_t', 'Region_t'}:
        raise TypeResolutionError(
            'Len_t, Size_t y Region_t solo pueden aparecer como parametros especiales '
            'de una funcion'
        )
    array_lengths = tuple(_constant_dimension_value(suffix) for suffix in suffixes)
    for length in array_lengths:
        if length is not None and length < 1:
            raise TypeResolutionError(
                f'El tamano de un array debe ser mayor que cero: {length}'
            )

    if base_name == 'buffer':
        if pointer_level:
            raise TypeResolutionError(
                'buffer no puede declararse como puntero; su almacenamiento ya '
                'es dinamico'
            )
        if len(array_lengths) != 1:
            raise TypeResolutionError(
                'buffer requiere exactamente una capacidad: buffer[N] o buffer[]'
            )
        capacity = array_lengths[0]
        max_capacity = (1 << (pointer_size * 8)) - 1
        if capacity is not None and capacity > max_capacity:
            raise TypeResolutionError(
                f'La capacidad de buffer no cabe en usize ({pointer_size * 8} bits)'
            )
        return TypeSpec(
            name='buffer',
            pointer_level=0,
            array_depth=0,
            value_is_const=_type_is_const(type_node),
            pointer_is_const=pointer_is_const,
            array_lengths=array_lengths,
            is_unique=unique,
        )

    array_depth = len(array_lengths)
    if array_depth > 3:
        raise TypeResolutionError(
            'Bagron admite matrices de hasta tres dimensiones; '
            f'{text} excede la profundidad maxima'
        )
    if array_depth > 1 and any(length is None for length in array_lengths):
        raise TypeResolutionError(
            'La matriz debe declarar todas sus dimensiones; '
            f'{text} no es un tipo de matriz valido'
        )
    if base_name == 'chain' and _type_is_const(type_node):
        raise TypeResolutionError(
            'chain ya es constante; no puede declararse const chain'
        )
    if base_name == 'chain' and (array_depth or pointer_level):
        raise TypeResolutionError(
            'chain es una cadena estatica y no puede combinarse con arrays ni punteros'
        )
    bit_width = None
    signed = None

    if base_name in {'usize', 'isize'}:
        if pointer_size not in {4, 8}:
            raise TypeResolutionError(
                f'El tamano de puntero del target no es valido: {pointer_size} bytes'
            )
        bit_width = pointer_size * 8
        signed = base_name == 'isize'

    match = re.fullmatch(r'(Bint|uBint)<(\d+)>', base_name)
    if match is not None:
        if not allow_bit_types:
            raise TypeResolutionError(
                'Bint<n> y uBint<n> solo pueden usarse como campos de flags'
            )
        base_name = match.group(1)
        bit_width = int(match.group(2))
        signed = base_name == 'Bint'
        minimum_width = 2 if base_name == 'Bint' else 1
        if bit_width < minimum_width:
            if base_name == 'Bint':
                raise TypeResolutionError(
                    f'El ancho de Bint debe ser de al menos 2 bits: {bit_width}'
                )
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
        array_lengths=array_lengths,
        is_unique=unique,
    )


def _namespace_owner(
    namespace: Mapping[str, object] | Callable[[str], object | None],
) -> object | None:
    """Return the Storage behind a bound ``Storage.resolve`` callable."""
    return getattr(namespace, '__self__', None)


def _resolve_aggregate(
    namespace: Mapping[str, object] | Callable[[str], object | None],
    name: str,
) -> AggregateSymbol | None:
    owner = _namespace_owner(namespace)
    resolver = getattr(owner, 'resolve_type', None)
    aggregate = resolver(name) if callable(resolver) else None
    return aggregate if isinstance(aggregate, AggregateSymbol) else None

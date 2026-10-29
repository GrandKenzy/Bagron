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
) -> object | None:
    if functions is None:
        return None
    return _resolve_symbol(functions, name)


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
) -> TypeSpec:
    text = _type_name(type_node)
    match = re.fullmatch(r'(.+?)((?:\[\d*\])*)', text)
    if match is None:
        raise TypeResolutionError(f'Tipo invalido: {text or "<vacio>"}')

    base_name = match.group(1)
    if base_name == 'int':
        raise TypeResolutionError(
            'El tipo int fue eliminado; usa int8, int16, int32 o int64'
        )
    if base_name == 'uint':
        raise TypeResolutionError(
            'El tipo uint fue eliminado; usa uint8, uint16, uint32 o uint64'
        )
    if base_name == 'wsize':
        raise TypeResolutionError(
            'El tipo wsize fue eliminado; usa usize o isize segun el signo'
        )
    if base_name in {'Len_t', 'Size_t'}:
        raise TypeResolutionError(
            'Len_t y Size_t solo pueden aparecer como parametros especiales '
            'de una funcion'
        )
    array_lengths = tuple(
        int(length) if length else None
        for length in re.findall(r'\[(\d*)\]', match.group(2))
    )
    for length in array_lengths:
        if length is not None and length < 1:
            raise TypeResolutionError(
                f'El tamano de un array debe ser mayor que cero: {length}'
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


def _resolve_method_call(
    namespace: Mapping[str, object] | Callable[[str], object | None],
    primary: object,
    suffixes: list[object],
    current_function: object | None = None,
) -> object | None:
    """Resolve a class method without exposing its hidden receiver in source."""
    owner = _namespace_owner(namespace)
    resolver = getattr(owner, 'resolve_method', None)
    if not callable(resolver):
        return None

    member_suffix = next(
        (
            suffix for suffix in reversed(suffixes)
            if getattr(suffix, 'name', None) == 'MEMBER_ACCESS'
        ),
        None,
    )
    if member_suffix is not None:
        base_name = _identifier_from_node(primary)
        member_name = _identifier_from_node(member_suffix)
        if not base_name or not member_name:
            return None
        base = _resolve_symbol(namespace, base_name)
        type_name = getattr(getattr(base, 'type_spec', None), 'name', None)
        class_reference = False
        if type_name is None and _resolve_aggregate(namespace, base_name) is not None:
            type_name = base_name
            class_reference = True
        if type_name is None:
            return None
        method = resolver(type_name, member_name)
        if (
            method is not None
            and class_reference
            and not getattr(method, 'is_static', False)
        ):
            raise ValueResolutionError(
                f'El metodo {type_name}.{member_name} requiere una instancia'
            )
        if (
            method is not None
            and not class_reference
            and getattr(method, 'is_static', False)
        ):
            raise ValueResolutionError(
                f'El metodo estatico {type_name}.{member_name} debe llamarse '
                f'como {type_name}.{member_name}'
            )
        return method

    owner_type = getattr(current_function, 'owner_type', None)
    method_name = _identifier_from_node(primary)
    if owner_type and method_name:
        method = resolver(owner_type, method_name)
        if (
            method is not None
            and getattr(current_function, 'is_static', False)
            and not getattr(method, 'is_static', False)
        ):
            raise ValueResolutionError(
                f'El metodo {owner_type}.{method_name} requiere una instancia'
            )
        if method is not None and getattr(method, 'is_static', False):
            raise ValueResolutionError(
                f'El metodo estatico {owner_type}.{method_name} debe llamarse '
                f'como {owner_type}.{method_name}'
            )
        return method
    return None


def _class_instance_type(
    namespace: Mapping[str, object] | Callable[[str], object | None],
    value: ValueInfo,
) -> AggregateSymbol | None:
    if (
        value.type_spec.pointer_level
        or value.type_spec.array_depth
    ):
        return None
    aggregate = _resolve_aggregate(namespace, value.type_spec.name)
    return (
        aggregate
        if aggregate is not None and aggregate.is_class
        else None
    )


def _infer_magic_operator(
    operator_names: tuple[str, ...],
    left: ValueInfo,
    right: ValueInfo | None,
    namespace: Mapping[str, object] | Callable[[str], object | None],
    functions: Mapping[str, object] | Callable[[str], object | None] | None,
    *,
    current_function: object | None = None,
) -> ValueInfo | None:
    aggregate = _class_instance_type(namespace, left)
    if aggregate is None:
        return None
    if getattr(current_function, 'is_method', False):
        return None

    owner = _namespace_owner(namespace)
    resolver = getattr(owner, 'resolve_method', None)
    if not callable(resolver):
        return None
    method = next(
        (
            resolver(aggregate.name, name)
            for name in operator_names
            if resolver(aggregate.name, name) is not None
        ),
        None,
    )
    if method is None:
        return None
    if getattr(method, 'is_static', False):
        raise ValueResolutionError(
            f'El metodo {aggregate.name}.{method.source_name} requiere '
            'una instancia implicita'
        )
    if getattr(method, 'is_unsafe', False) and not _unsafe_context(
        current_function
    ):
        raise ValueResolutionError(
            f'La funcion segura no puede llamar a {aggregate.name}.'
            f'{method.source_name} porque es @unsafe'
        )

    parameters = getattr(method.signature, 'parameters', ())
    visible_parameters = _visible_parameters(parameters)
    explicit_parameters = [
        parameter for parameter in parameters
        if not getattr(parameter, 'is_receiver', False)
    ]
    expected_count = 1 if right is not None else 0
    if (
        len(visible_parameters) != expected_count
        or len(explicit_parameters) != expected_count
        or any(
            parameter.is_length or parameter.is_size
            for parameter in explicit_parameters
        )
    ):
        raise ValueResolutionError(
            f'El metodo magico {aggregate.name}.{method.source_name} tiene una '
            f'firma invalida para este operador (se esperaban {expected_count} '
            'parametros)'
        )
    if right is not None:
        parameter = visible_parameters[0]
        _validate_array_argument_storage(
            f'{aggregate.name}.{method.source_name}',
            parameter,
            right,
        )
        if not is_compatible(parameter.type_spec, right):
            raise ValueResolutionError(
                f'El operando derecho de {aggregate.name}.{method.source_name} '
                f'no coincide con {parameter.type_spec.canonical_name}'
            )

    return_type = getattr(method.signature, 'return_type', TypeSpec('void'))
    if (
        return_type.name == 'void'
        and return_type.pointer_level == 0
        and return_type.array_depth == 0
    ):
        raise ValueResolutionError(
            f'El metodo magico {aggregate.name}.{method.source_name} debe '
            'retornar un valor'
        )
    return ValueInfo(
        return_type,
        address_origin='unknown' if return_type.pointer_level else None,
    )


def _constructor_parameters(
    aggregate: AggregateSymbol | None,
) -> tuple[object, ...] | None:
    if aggregate is None:
        return None
    parameters = getattr(aggregate, 'constructor_parameters', None)
    return parameters if parameters is not None else None


def _infer_constructor_call(
    name: str,
    aggregate: AggregateSymbol,
    argument_items: list[object],
    namespace: Mapping[str, object] | Callable[[str], object | None],
    functions: Mapping[str, object] | Callable[[str], object | None] | None,
    *,
    current_function: object | None = None,
) -> ValueInfo:
    parameters = _constructor_parameters(aggregate)
    if parameters is None:
        initializer_name = getattr(aggregate, 'initializer_name', None) or '__init__'
        raise ValueResolutionError(
            f'La clase {name} no tiene un {initializer_name} utilizable'
        )

    visible_parameters = _visible_parameters(parameters)
    if len(argument_items) != len(visible_parameters):
        raise ValueResolutionError(
            f'El constructor {name} esperaba {len(visible_parameters)} '
            f'argumentos y recibio {len(argument_items)}'
        )

    argument_infos: dict[str, ValueInfo] = {}
    for parameter, argument in zip(visible_parameters, argument_items):
        argument_info = infer_value(
            argument,
            namespace,
            functions,
            current_function=current_function,
        )
        argument_infos[parameter.name] = argument_info
        _validate_array_argument_storage(name, parameter, argument_info)
        if not is_compatible(parameter.type_spec, argument_info):
            raise ValueResolutionError(
                f'El argumento de {name} no coincide con '
                f'{parameter.type_spec.canonical_name}'
            )

    _validate_expansion_parameters(
        name,
        parameters,
        argument_infos,
        current_function=current_function,
    )
    return ValueInfo(TypeSpec(aggregate.name))


def _deref_type(type_spec: TypeSpec) -> TypeSpec:
    if type_spec.pointer_level < 1:
        raise ValueResolutionError(
            'la desreferenciacion requiere un valor puntero'
        )
    if (
        type_spec.name == 'void'
        and type_spec.pointer_level == 1
        and type_spec.array_depth == 0
    ):
        raise ValueResolutionError(
            'void* no puede desreferenciarse sin conocer el tipo apuntado'
        )
    return TypeSpec(
        name=type_spec.name,
        bit_width=type_spec.bit_width,
        signed=type_spec.signed,
        pointer_level=type_spec.pointer_level - 1,
        array_depth=type_spec.array_depth,
        value_is_const=type_spec.value_is_const,
        array_lengths=type_spec.array_lengths,
    )


def _address_type(type_spec: TypeSpec) -> TypeSpec:
    if type_spec.name == 'chain':
        raise ValueResolutionError(
            'chain no puede usarse como una direccion en esta fase'
        )
    if type_spec.array_depth:
        raise ValueResolutionError(
            'un array debe direccionar un elemento, por ejemplo $data[0]'
        )
    return TypeSpec(
        name=type_spec.name,
        bit_width=type_spec.bit_width,
        signed=type_spec.signed,
        pointer_level=type_spec.pointer_level + 1,
        value_is_const=type_spec.value_is_const,
        array_lengths=type_spec.array_lengths,
    )


def _deref_value(value: ValueInfo) -> ValueInfo:
    origin = value.address_origin
    return ValueInfo(
        type_spec=_deref_type(value.type_spec),
        is_lvalue=True,
        address_origin=origin,
        storage_origin=origin,
        pointer_provenance_unknown=value.pointer_provenance_unknown,
    )


def _suffix_value(suffix: object) -> object | None:
    return next(
        (
            child for child in _children(suffix)
            if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
        ),
        None,
    )


def _call_arguments(call_suffix: object) -> list[object]:
    arguments = next(
        (
            child for child in _children(call_suffix)
            if isinstance(child, gast.ASTRef) and child.name == 'ARGUMENTS'
        ),
        None,
    )
    if arguments is None:
        return []
    container = next(iter(_children(arguments)), None)
    return _children(container)


def _visible_parameters(parameters: object) -> list[object]:
    return [
        parameter for parameter in parameters
        if not (
            getattr(parameter, 'is_length', False)
            or getattr(parameter, 'is_size', False)
            or getattr(parameter, 'is_receiver', False)
        )
    ]


def _validate_array_argument_storage(
    function_name: str,
    parameter: object,
    argument: ValueInfo,
) -> None:
    """Require addressable storage for arrays passed by reference."""
    type_spec = getattr(parameter, 'type_spec', TypeSpec('void'))
    if type_spec.array_depth and not argument.is_lvalue:
        raise ValueResolutionError(
            f'El argumento de {function_name} para {getattr(parameter, "name", "<array>")} '
            'debe ser una variable de array con almacenamiento propio'
        )


def _validate_expansion_parameters(
    function_name: str,
    parameters: object,
    argument_infos: Mapping[str, ValueInfo],
    current_function: object | None = None,
) -> None:
    """Ensure compiler-supplied lengths and sizes have valid sources."""

    def forwarded_expansion(
        source: ValueInfo | None,
        *,
        is_length: bool,
    ) -> bool:
        source_name = getattr(source, 'identifier', None)
        signature = getattr(current_function, 'signature', None)
        if not source_name or signature is None:
            return False
        return any(
            getattr(parameter, 'is_length', False) == is_length
            and getattr(parameter, 'is_size', False) == (not is_length)
            and getattr(parameter, 'length_of', None) == source_name
            for parameter in getattr(signature, 'parameters', ())
        )

    for parameter in parameters:
        is_length = getattr(parameter, 'is_length', False)
        is_size = getattr(parameter, 'is_size', False)
        if not (is_length or is_size):
            continue
        source_name = getattr(parameter, 'length_of', None)
        source = argument_infos.get(source_name or '')
        source_type = source.type_spec if source is not None else None
        if is_length and source_type is not None and source_type.name == 'chain':
            if (
                source is None
                or (
                    source.is_literal
                    and not isinstance(source.value, str)
                )
                or (
                    not source.is_literal
                    and not forwarded_expansion(source, is_length=True)
                )
            ):
                raise ValueResolutionError(
                    f'Len_t de {function_name} requiere que {source_name} '
                    'sea un chain constante o un chain con Len_t propagado'
                )
            continue
        array_length = (
            source_type.array_lengths[0]
            if source_type is not None
            and source_type.array_depth > 0
            and not source_type.pointer_level
            and source_type.array_lengths
            else None
        )
        if (
            is_length
            and array_length is None
            and not forwarded_expansion(source, is_length=True)
        ):
            raise ValueResolutionError(
                f'Len_t de {function_name} requiere que {source_name} '
                'sea un array con longitud conocida en compilacion'
            )
        if is_size and source_type is None:
            raise ValueResolutionError(
                f'Size_t de {function_name} no tiene un valor fuente valido'
            )
        if is_size and source_type.array_depth > 0 and not source_type.pointer_level:
            if (
                (
                    not source_type.array_lengths
                    or any(length is None for length in source_type.array_lengths)
                )
                and not forwarded_expansion(source, is_length=False)
            ):
                raise ValueResolutionError(
                    f'Size_t de {function_name} requiere que {source_name} '
                    'sea un array con longitud conocida en compilacion'
                )


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


def _infer_postfix(
    current: gast.ASTRef,
    namespace: Mapping[str, object] | Callable[[str], object | None],
    functions: Mapping[str, object] | Callable[[str], object | None] | None,
    current_function: object | None = None,
) -> ValueInfo:
    children = _children(current)
    primary = children[0] if children else None
    suffixes: list[object] = []
    for child in children[1:]:
        suffixes.extend(_children(child) if isinstance(child, list) else [child])

    call_suffix = next(
        (
            suffix for suffix in suffixes
            if isinstance(suffix, gast.ASTRef) and suffix.name == 'CALL_SUFFIX'
        ),
        None,
    )
    if call_suffix is not None:
        name = _identifier_from_node(primary)
        for suffix in suffixes:
            if (
                isinstance(suffix, gast.ASTRef)
                and suffix.name == 'MEMBER_ACCESS'
            ):
                member = _identifier_from_node(suffix)
                if member is not None:
                    name = f'{name}.{member}' if name else member
        aggregate = _resolve_aggregate(namespace, name or '')
        if aggregate is not None:
            return _infer_constructor_call(
                name or aggregate.name,
                aggregate,
                _call_arguments(call_suffix),
                namespace,
                functions,
                current_function=current_function,
            )
        function = _resolve_method_call(
            namespace,
            primary,
            suffixes,
            current_function=current_function,
        )
        if function is None:
            function = _resolve_function(functions, name or '')
        if function is None:
            raise ValueResolutionError(f'La funcion no existe: {name or "<anonima>"}')
        if getattr(function, 'is_unsafe', False) and not _unsafe_context(
            current_function
        ):
            raise ValueResolutionError(
                f'La funcion segura no puede llamar a {name} porque es @unsafe'
            )

        argument_items = _call_arguments(call_suffix)

        signature = getattr(function, 'signature', None)
        parameters = getattr(signature, 'parameters', ())
        visible_parameters = _visible_parameters(parameters)
        if len(argument_items) != len(visible_parameters):
            raise ValueResolutionError(
                f'La funcion {name} esperaba {len(visible_parameters)} argumentos y '
                f'recibio {len(argument_items)}'
            )
        argument_infos: dict[str, ValueInfo] = {}
        for parameter, argument in zip(visible_parameters, argument_items):
            argument_info = infer_value(
                argument,
                namespace,
                functions,
                current_function=current_function,
            )
            argument_infos[parameter.name] = argument_info
            _validate_array_argument_storage(name, parameter, argument_info)
            if not is_compatible(parameter.type_spec, argument_info):
                raise ValueResolutionError(
                    f'El argumento de {name} no coincide con '
                    f'{parameter.type_spec.canonical_name}'
                )
            if (
                argument_info.type_spec.pointer_level > 0
                and argument_info.address_origin == 'local'
                and getattr(signature, 'return_type', TypeSpec('void')).pointer_level
                > 0
                and not _unsafe_context(current_function)
            ):
                raise ValueResolutionError(
                    f'La direccion local pasada a {name} no puede escapar '
                    'a traves de un retorno puntero'
                )
        _validate_expansion_parameters(
            name,
            parameters,
            argument_infos,
            current_function=current_function,
        )
        return_type = getattr(signature, 'return_type', TypeSpec('void'))
        if (
            return_type.name == 'void'
            and return_type.pointer_level == 0
            and return_type.array_depth == 0
        ):
            raise ValueResolutionError(
                'una funcion void solo puede llamarse como sentencia'
            )
        if (
            return_type.name == 'Never'
            and return_type.pointer_level == 0
            and return_type.array_depth == 0
        ):
            raise ValueResolutionError(
                'una funcion Never solo puede llamarse como sentencia'
            )
        result = ValueInfo(
            return_type,
            address_origin='unknown' if return_type.pointer_level else None,
        )
        # Member accesses before the call are part of a qualified function
        # name (for example ``m.doble(3)``), not accesses on the returned
        # value.  Only suffixes after the call may be applied to its result.
        call_index = suffixes.index(call_suffix)
        trailing = suffixes[call_index + 1:]
        if not trailing:
            return result
        # Function-return access is resolved by applying the same postfix
        # rules to the returned value.  This keeps calls and memory accesses
        # composable without inventing a second expression model.
        for suffix in trailing:
            if getattr(suffix, 'name', None) == 'INDEX_ACCESS':
                index_node = _suffix_value(suffix)
                if index_node is None:
                    raise ValueResolutionError('El indice no contiene una expresion')
                index = infer_value(
                    index_node,
                    namespace,
                    functions,
                    current_function=current_function,
                )
                if not _is_integer_scalar(index.type_spec):
                    raise ValueResolutionError('El indice debe ser un entero escalar')
                if result.type_spec.array_depth:
                    _validate_array_index(result, index, current_function)
                    result = ValueInfo(
                        TypeSpec(
                            name=result.type_spec.name,
                            bit_width=result.type_spec.bit_width,
                            signed=result.type_spec.signed,
                            pointer_level=result.type_spec.pointer_level,
                            array_depth=result.type_spec.array_depth - 1,
                            value_is_const=result.type_spec.value_is_const,
                            array_lengths=result.type_spec.array_lengths[1:],
                        ),
                        is_lvalue=True,
                        address_origin=result.address_origin,
                        storage_origin=result.storage_origin or result.address_origin,
                        identifier=result.identifier,
                        address_path=(*result.address_path, ('index', index)),
                    )
                elif result.type_spec.name == 'chain':
                    if not _unsafe_context(current_function):
                        raise ValueResolutionError(
                            'la indexacion de chain requiere @unsafe'
                        )
                    result = ValueInfo(
                        TypeSpec('char'),
                        is_lvalue=True,
                        address_origin=result.address_origin,
                        storage_origin=result.storage_origin or result.address_origin,
                        identifier=result.identifier,
                        address_path=(*result.address_path, ('index', index)),
                    )
                elif result.type_spec.pointer_level:
                    if not _unsafe_context(current_function):
                        raise ValueResolutionError(
                            'la indexacion de punteros crudos requiere @unsafe'
                        )
                    result = _deref_value(result)
                else:
                    raise ValueResolutionError('El valor no es indexable')
            elif getattr(suffix, 'name', None) == 'MEMBER_ACCESS':
                result = _member_value(
                    result,
                    suffix,
                    namespace,
                    current_function=current_function,
                )
        return result

    result = infer_value(
        primary,
        namespace,
        functions,
        current_function=current_function,
    )
    for suffix in suffixes:
        name = getattr(suffix, 'name', None)
        if name == 'INDEX_ACCESS':
            index_node = _suffix_value(suffix)
            if index_node is None:
                raise ValueResolutionError('El indice no contiene una expresion')
            index = infer_value(
                index_node,
                namespace,
                functions,
                current_function=current_function,
            )
            if not _is_integer_scalar(index.type_spec):
                raise ValueResolutionError('El indice debe ser un entero escalar')
            if result.type_spec.array_depth:
                _validate_array_index(result, index, current_function)
                result = ValueInfo(
                    TypeSpec(
                        name=result.type_spec.name,
                        bit_width=result.type_spec.bit_width,
                        signed=result.type_spec.signed,
                        pointer_level=result.type_spec.pointer_level,
                        array_depth=result.type_spec.array_depth - 1,
                        value_is_const=result.type_spec.value_is_const,
                        array_lengths=result.type_spec.array_lengths[1:],
                    ),
                    is_lvalue=True,
                    address_origin=result.address_origin,
                    storage_origin=result.storage_origin or result.address_origin,
                    identifier=result.identifier,
                    address_path=(*result.address_path, ('index', index)),
                )
            elif result.type_spec.name == 'chain':
                if not _unsafe_context(current_function):
                    raise ValueResolutionError(
                        'la indexacion de chain requiere @unsafe'
                    )
                result = ValueInfo(
                    TypeSpec('char'),
                    is_lvalue=True,
                    address_origin=result.address_origin,
                    storage_origin=result.storage_origin or result.address_origin,
                    identifier=result.identifier,
                    address_path=(*result.address_path, ('index', index)),
                )
            elif result.type_spec.pointer_level:
                if not _unsafe_context(current_function):
                    raise ValueResolutionError(
                        'la indexacion de punteros crudos requiere @unsafe'
                    )
                result = _deref_value(result)
            else:
                raise ValueResolutionError('El valor no es indexable')
        elif name == 'MEMBER_ACCESS':
            result = _member_value(
                result,
                suffix,
                namespace,
                current_function=current_function,
            )
    return result


def infer_call(
    node: object,
    namespace: Mapping[str, object] | Callable[[str], object | None],
    functions: Mapping[str, object] | Callable[[str], object | None] | None = None,
    *,
    current_function: object | None = None,
) -> ValueInfo:
    """Validate a call that appears as a standalone statement.

    Calls used inside expressions are checked by ``_infer_postfix``.  A CALL
    node has the same primary/suffix layout but is not wrapped in a
    POSTFIX_EXPR, so it needs this small entry point to enforce the same
    unsafe boundary and argument rules.
    """
    children = _children(node)
    primary = children[0] if children else None
    suffixes: list[object] = []
    for child in children[1:]:
        suffixes.extend(_children(child) if isinstance(child, list) else [child])

    call_suffix = next(
        (
            suffix for suffix in suffixes
            if isinstance(suffix, gast.ASTRef) and suffix.name == 'CALL_SUFFIX'
        ),
        None,
    )
    if call_suffix is None:
        raise ValueResolutionError('La llamada no tiene argumentos')

    name = _identifier_from_node(primary)
    for suffix in suffixes:
        if (
            isinstance(suffix, gast.ASTRef)
            and suffix.name == 'MEMBER_ACCESS'
        ):
            member = _identifier_from_node(suffix)
            if member is not None:
                name = f'{name}.{member}' if name else member

    aggregate = _resolve_aggregate(namespace, name or '')
    if aggregate is not None:
        return _infer_constructor_call(
            name or aggregate.name,
            aggregate,
            _call_arguments(call_suffix),
            namespace,
            functions,
            current_function=current_function,
        )

    function = _resolve_method_call(
        namespace,
        primary,
        suffixes,
        current_function=current_function,
    )
    if function is None:
        function = _resolve_function(functions, name or '')
    if function is None:
        raise ValueResolutionError(f'La funcion no existe: {name or "<anonima>"}')
    if getattr(function, 'is_unsafe', False) and not _unsafe_context(
        current_function
    ):
        raise ValueResolutionError(
            f'La funcion segura no puede llamar a {name} porque es @unsafe'
        )

    argument_items = _call_arguments(call_suffix)

    signature = getattr(function, 'signature', None)
    parameters = getattr(signature, 'parameters', ())
    visible_parameters = _visible_parameters(parameters)
    if len(argument_items) != len(visible_parameters):
        raise ValueResolutionError(
            f'La funcion {name} esperaba {len(visible_parameters)} argumentos y '
            f'recibio {len(argument_items)}'
        )
    argument_infos: dict[str, ValueInfo] = {}
    for parameter, argument in zip(visible_parameters, argument_items):
        argument_info = infer_value(
            argument,
            namespace,
            functions,
            current_function=current_function,
        )
        argument_infos[parameter.name] = argument_info
        _validate_array_argument_storage(name, parameter, argument_info)
        if not is_compatible(parameter.type_spec, argument_info):
            raise ValueResolutionError(
                f'El argumento de {name} no coincide con '
                f'{parameter.type_spec.canonical_name}'
            )
        if (
            argument_info.type_spec.pointer_level > 0
            and argument_info.address_origin == 'local'
            and getattr(signature, 'return_type', TypeSpec('void')).pointer_level
            > 0
            and not _unsafe_context(current_function)
        ):
            raise ValueResolutionError(
                f'La direccion local pasada a {name} no puede escapar '
                'a traves de un retorno puntero'
            )
    _validate_expansion_parameters(
        name,
        parameters,
        argument_infos,
        current_function=current_function,
    )

    return_type = getattr(signature, 'return_type', TypeSpec('void'))
    return ValueInfo(
        return_type,
        address_origin='unknown' if return_type.pointer_level else None,
    )


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


def infer_value(
    node: object,
    namespace: Mapping[str, object] | Callable[[str], object | None],
    functions: Mapping[str, object] | Callable[[str], object | None] | None = None,
    *,
    current_function: object | None = None,
) -> ValueInfo:
    current = _unwrap_value(node)

    if isinstance(current, gast.ASTRef) and current.name == 'LOGICAL_NOT':
        operand_node = next(
            (
                child for child in _children(current)
                if isinstance(child, gast.ASTRef)
            ),
            None,
        )
        if operand_node is None:
            raise ValueResolutionError(
                'la negacion logica requiere un operando'
            )
        operand = infer_value(
            operand_node,
            namespace,
            functions,
            current_function=current_function,
        )
        if not is_condition_type(operand.type_spec):
            raise ValueResolutionError(
                'el operando de una negacion logica debe ser bool'
            )
        if operand.is_literal:
            return ValueInfo(
                TypeSpec('bool'),
                is_literal=True,
                value=not bool(operand.value),
            )
        return ValueInfo(TypeSpec('bool'))

    if type(current).__name__ == 'ASTUnaryOp':
        operator = getattr(getattr(current.operator, 'token', None), 'name', None)
        operand = infer_value(
            current.operand,
            namespace,
            functions,
            current_function=current_function,
        )
        if operator == 'DOLLAR':
            if not operand.is_lvalue:
                raise ValueResolutionError(
                    'el operador $ requiere una variable o acceso direccionable'
                )
            if not operand.is_addressable:
                raise ValueResolutionError(
                    'un campo de flags no tiene una direccion independiente'
                )
            return ValueInfo(
                type_spec=_address_type(operand.type_spec),
                address_origin=operand.storage_origin or operand.address_origin,
                address_of=operand.identifier,
                address_path=operand.address_path,
            )
        if operator in LOGICAL_NOT_OPERATORS:
            if not is_condition_type(operand.type_spec):
                raise ValueResolutionError(
                    'el operando de una negacion logica debe ser bool'
                )
            if operand.is_literal:
                return ValueInfo(
                    TypeSpec('bool'),
                    is_literal=True,
                    value=not bool(operand.value),
                )
            return ValueInfo(TypeSpec('bool'))

        magic_result = _infer_magic_operator(
            MAGIC_UNARY_OPERATORS.get(operator, ()),
            operand,
            None,
            namespace,
            functions,
            current_function=current_function,
        )
        if magic_result is not None:
            return magic_result

        if not (
            (
                operand.type_spec.pointer_level == 0
                and operand.type_spec.array_depth == 0
                and operand.type_spec.name in INTEGER_TYPES
            )
            or _is_float_scalar(operand.type_spec)
        ):
            raise ValueResolutionError(
                'el operando de una operacion unaria debe ser entero o flotante'
            )
        if operator not in {'PLUS', 'MINUS'}:
            raise UnsupportedExpressionError(
                'solo se soportan signos unarios sobre enteros y flotantes'
            )
        if operand.is_literal:
            value = operand.value if operator == 'PLUS' else -operand.value
            return ValueInfo(
                operand.type_spec,
                is_literal=True,
                value=value,
            )
        return ValueInfo(operand.type_spec)

    if isinstance(current, gast.ASTRef) and current.name == 'PAREN_VALUE':
        inner = next(
            (
                child for child in _children(current)
                if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
            ),
            None,
        )
        if inner is None:
            raise ValueResolutionError('La expresion parentizada esta vacia')
        value = infer_value(
            inner,
            namespace,
            functions,
            current_function=current_function,
        )
        if value.type_spec.pointer_level:
            _require_known_pointer(value, current_function, 'la desreferenciacion')
            return _deref_value(value)
        return value

    if type(current).__name__ == 'ASTBinaryOp':
        left = infer_value(
            current.left,
            namespace,
            functions,
            current_function=current_function,
        )
        right = infer_value(
            current.right,
            namespace,
            functions,
            current_function=current_function,
        )
        operator = getattr(getattr(current.operator, 'token', None), 'name', None)

        magic_result = _infer_magic_operator(
            MAGIC_BINARY_OPERATORS.get(operator, ()),
            left,
            right,
            namespace,
            functions,
            current_function=current_function,
        )
        if magic_result is not None:
            return magic_result

        if operator in COMPARISON_OPERATORS:
            left_is_integer = (
                left.type_spec.pointer_level == 0
                and left.type_spec.array_depth == 0
                and left.type_spec.name in INTEGER_TYPES | {'char'}
            )
            right_is_integer = (
                right.type_spec.pointer_level == 0
                and right.type_spec.array_depth == 0
                and right.type_spec.name in INTEGER_TYPES | {'char'}
            )
            left_is_float = _is_float_scalar(left.type_spec)
            right_is_float = _is_float_scalar(right.type_spec)
            float_comparison = (
                (left_is_float and right_is_float)
                or (
                    left_is_float
                    and right.is_literal
                    and right.type_spec.name == 'int32'
                )
                or (
                    right_is_float
                    and left.is_literal
                    and left.type_spec.name == 'int32'
                )
            )
            both_bool = (
                left.type_spec.name == 'bool'
                and right.type_spec.name == 'bool'
            )
            if not (
                (left_is_integer and right_is_integer)
                or float_comparison
                or both_bool
            ):
                raise ValueResolutionError(
                    'los operandos de una comparacion deben ser enteros, '
                    'flotantes o bool'
                )
            if (
                left.type_spec.name in INTEGER_TYPES
                and right.type_spec.name in INTEGER_TYPES
                and _integer_common_type(left, right) is None
            ):
                raise ValueResolutionError(
                    'los operandos enteros deben conservar el signo y permitir '
                    'un ensanchamiento seguro'
                )
            if left.is_literal and right.is_literal:
                operations = {
                    'EQUAL': lambda: left.value == right.value,
                    'NOT_EQUAL': lambda: left.value != right.value,
                    'LESS': lambda: left.value < right.value,
                    'LESS_EQUAL': lambda: left.value <= right.value,
                    'GREATER': lambda: left.value > right.value,
                    'GREATER_EQUAL': lambda: left.value >= right.value,
                }
                return ValueInfo(
                    TypeSpec('bool'),
                    is_literal=True,
                    value=operations[operator](),
                )
            return ValueInfo(TypeSpec('bool'))

        if operator in LOGICAL_OPERATORS:
            if not is_condition_type(left.type_spec) or not is_condition_type(
                right.type_spec
            ):
                raise ValueResolutionError(
                    'los operandos logicos deben ser bool'
                )
            if left.is_literal and right.is_literal:
                if operator in {'AND_LOGIC', 'LOGIC_AND'}:
                    value = bool(left.value) and bool(right.value)
                else:
                    value = bool(left.value) or bool(right.value)
                return ValueInfo(TypeSpec('bool'), is_literal=True, value=value)
            return ValueInfo(TypeSpec('bool'))

        if operator in BITWISE_OPERATORS:
            left_is_integer = (
                left.type_spec.pointer_level == 0
                and left.type_spec.array_depth == 0
                and left.type_spec.name in INTEGER_TYPES
            )
            right_is_integer = (
                right.type_spec.pointer_level == 0
                and right.type_spec.array_depth == 0
                and right.type_spec.name in INTEGER_TYPES
            )
            if not (left_is_integer and right_is_integer):
                raise ValueResolutionError(
                    'los operandos bitwise deben ser enteros escalares'
                )
            result_type = _integer_common_type(left, right)
            if result_type is None:
                raise ValueResolutionError(
                    'los operandos bitwise deben conservar el signo y permitir '
                    'un ensanchamiento seguro'
                )
            if left.is_literal and right.is_literal:
                operations = {
                    'AND': lambda: left.value & right.value,
                    'OR': lambda: left.value | right.value,
                    'XOR': lambda: left.value ^ right.value,
                    'SHL': lambda: left.value << right.value,
                    'SHR': lambda: left.value >> right.value,
                }
                try:
                    value = operations[operator]()
                except (KeyError, ValueError):
                    raise ValueResolutionError(
                        'la operacion bitwise no es valida'
                    ) from None
                return ValueInfo(
                    result_type,
                    is_literal=True,
                    value=value,
                )
            return ValueInfo(result_type)

        if operator not in {'PLUS', 'MINUS', 'STAR', 'SLASH', 'PERCENT'}:
            raise UnsupportedExpressionError(
                'solo se soportan operaciones aritmeticas enteras o flotantes'
            )
        left_is_int = (
            left.type_spec.pointer_level == 0
            and left.type_spec.array_depth == 0
            and left.type_spec.name in INTEGER_TYPES
        )
        right_is_int = (
            right.type_spec.pointer_level == 0
            and right.type_spec.array_depth == 0
            and right.type_spec.name in INTEGER_TYPES
        )
        left_is_float = _is_float_scalar(left.type_spec)
        right_is_float = _is_float_scalar(right.type_spec)
        float_arithmetic = (
            (left_is_float and right_is_float)
            or (left_is_float and right.is_literal and right_is_int)
            or (right_is_float and left.is_literal and left_is_int)
        )
        if not float_arithmetic and not (left_is_int and right_is_int):
            raise ValueResolutionError(
                'los operandos de una operacion aritmetica deben ser enteros o '
                'flotantes compatibles'
            )

        if float_arithmetic:
            if left_is_float and right_is_float:
                result_type = (
                    left.type_spec
                    if _float_rank(left.type_spec) >= _float_rank(right.type_spec)
                    else right.type_spec
                )
            elif left_is_float:
                result_type = left.type_spec
            else:
                result_type = right.type_spec
            if left.is_literal and right.is_literal:
                operations = {
                    'PLUS': lambda: left.value + right.value,
                    'MINUS': lambda: left.value - right.value,
                    'STAR': lambda: left.value * right.value,
                    'SLASH': lambda: left.value / right.value,
                    'PERCENT': lambda: left.value % right.value,
                }
                try:
                    value = operations[operator]()
                except (KeyError, ZeroDivisionError) as error:
                    raise ValueResolutionError(
                        'la operacion aritmetica flotante no es valida'
                    ) from error
                return ValueInfo(
                    result_type,
                    is_literal=True,
                    value=value,
                )
            return ValueInfo(result_type)

        result_type = _integer_common_type(left, right)
        if result_type is None:
            raise ValueResolutionError(
                'los operandos enteros deben conservar el signo y permitir '
                'un ensanchamiento seguro'
            )

        if left.is_literal and right.is_literal:
            operations = {
                'PLUS': lambda: left.value + right.value,
                'MINUS': lambda: left.value - right.value,
                'STAR': lambda: left.value * right.value,
                'SLASH': lambda: left.value // right.value,
                'PERCENT': lambda: left.value % right.value,
            }
            try:
                value = operations[operator]()
            except (KeyError, ZeroDivisionError) as error:
                raise ValueResolutionError(
                    'la operacion aritmetica no es valida'
                ) from error
            return ValueInfo(result_type, is_literal=True, value=value)
        return ValueInfo(result_type)

    if isinstance(current, gast.ASTRef) and current.name == 'POSTFIX_EXPR':
        return _infer_postfix(
            current,
            namespace,
            functions,
            current_function=current_function,
        )

    if isinstance(current, gast.ASTRef) and current.name == 'ARRAY_VALUE':
        array_node = next(iter(_children(current)), None)
        items = tuple(
            infer_value(
                item,
                namespace,
                functions,
                current_function=current_function,
            )
            for item in _children(array_node)
        )
        item_type = items[0].type_spec if items else TypeSpec('array')
        return ValueInfo(
            type_spec=TypeSpec(
                name=item_type.name,
                bit_width=item_type.bit_width,
                signed=item_type.signed,
                array_depth=item_type.array_depth + 1,
                array_lengths=(len(items), *item_type.array_lengths),
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
        initialized = getattr(symbol, 'value_info', None)
        constant_literal = bool(
            getattr(symbol, 'value_is_const', False)
            and initialized is not None
            and initialized.is_literal
        )
        pointer_origin = None
        if symbol.type_spec.pointer_level:
            pointer_origin = (
                getattr(initialized, 'address_origin', None)
                if initialized is not None
                else 'unknown'
            )
            if pointer_origin is None and initialized is not None:
                # A literal Null has no storage lifetime to escape.  Other
                # unresolved pointer values remain conservatively unknown.
                pointer_origin = (
                    None
                    if getattr(initialized.type_spec, 'name', None) == 'Null'
                    else 'unknown'
                )
            elif pointer_origin is None:
                pointer_origin = 'unknown'

        return ValueInfo(
            type_spec=symbol.type_spec,
            identifier=str(value),
            value=(initialized.value if constant_literal else symbol.value),
            is_literal=constant_literal,
            is_lvalue=True,
            address_origin=(
                pointer_origin
                if symbol.type_spec.pointer_level
                else getattr(symbol, 'scope_kind', None)
            ),
            storage_origin=getattr(symbol, 'scope_kind', None),
            address_path=(),
        )

    if kind == 'BOOL' or isinstance(value, bool):
        return ValueInfo(TypeSpec('bool'), is_literal=True, value=value)

    if kind == 'STRING':
        return ValueInfo(TypeSpec('chain'), is_literal=True, value=value)

    if kind == 'NULL':
        return ValueInfo(TypeSpec('Null'), is_literal=True, value=value)

    if kind in ('NUMBER', 'DECIMAL'):
        number_type = 'float' if isinstance(value, float) else 'int32'
        return ValueInfo(TypeSpec(number_type), is_literal=True, value=value)

    raise UnsupportedExpressionError('el inicializador no es un literal compatible')


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

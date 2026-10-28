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
SIGNED_INTEGER_TYPES = {'int', 'int8', 'int16', 'int32', 'int64', 'Bint'}
UNSIGNED_INTEGER_TYPES = {'uint', 'uint8', 'uint16', 'uint32', 'uint64', 'byte', 'uBint'}
INTEGER_TYPES = SIGNED_INTEGER_TYPES | UNSIGNED_INTEGER_TYPES
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


def is_condition_type(type_spec: TypeSpec) -> bool:
    """Return whether a value can be used as a control-flow condition."""
    return (
        type_spec.pointer_level == 0
        and type_spec.array_depth == 0
        and (type_spec.name == 'bool' or type_spec.name in INTEGER_TYPES)
    )


def resolve_type(
    type_node: object,
    *,
    pointer_level: int = 0,
    pointer_is_const: bool = False,
) -> TypeSpec:
    text = _type_name(type_node)
    match = re.fullmatch(r'(.+?)((?:\[\d*\])*)', text)
    if match is None:
        raise TypeResolutionError(f'Tipo invalido: {text or "<vacio>"}')

    base_name = match.group(1)
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
    if base_name == 'chain' and (array_depth or pointer_level):
        raise TypeResolutionError(
            'chain es una cadena estatica y no puede combinarse con arrays ni punteros'
        )
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


def _deref_type(type_spec: TypeSpec) -> TypeSpec:
    if type_spec.pointer_level < 1:
        raise ValueResolutionError(
            'la desreferenciacion requiere un valor puntero'
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
    )


def _suffix_value(suffix: object) -> object | None:
    return next(
        (
            child for child in _children(suffix)
            if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
        ),
        None,
    )


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
        function = _resolve_function(functions, name or '')
        if function is None:
            raise ValueResolutionError(f'La funcion no existe: {name or "<anonima>"}')
        if getattr(function, 'is_unsafe', False) and not _unsafe_context(
            current_function
        ):
            raise ValueResolutionError(
                f'La funcion segura no puede llamar a {name} porque es @unsafe'
            )

        arguments = next(
            (
                child for child in _children(call_suffix)
                if isinstance(child, gast.ASTRef) and child.name == 'ARGUMENTS'
            ),
            None,
        )
        argument_items: list[object] = []
        if arguments is not None:
            container = next(iter(_children(arguments)), None)
            argument_items = _children(container)

        signature = getattr(function, 'signature', None)
        parameters = getattr(signature, 'parameters', ())
        if len(argument_items) != len(parameters):
            raise ValueResolutionError(
                f'La funcion {name} esperaba {len(parameters)} argumentos y '
                f'recibio {len(argument_items)}'
            )
        for parameter, argument in zip(parameters, argument_items):
            argument_info = infer_value(
                argument,
                namespace,
                functions,
                current_function=current_function,
            )
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
        return_type = getattr(signature, 'return_type', TypeSpec('void'))
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

    function = _resolve_function(functions, name or '')
    if function is None:
        raise ValueResolutionError(f'La funcion no existe: {name or "<anonima>"}')
    if getattr(function, 'is_unsafe', False) and not _unsafe_context(
        current_function
    ):
        raise ValueResolutionError(
            f'La funcion segura no puede llamar a {name} porque es @unsafe'
        )

    arguments = next(
        (
            child for child in _children(call_suffix)
            if isinstance(child, gast.ASTRef) and child.name == 'ARGUMENTS'
        ),
        None,
    )
    argument_items: list[object] = []
    if arguments is not None:
        container = next(iter(_children(arguments)), None)
        argument_items = _children(container)

    signature = getattr(function, 'signature', None)
    parameters = getattr(signature, 'parameters', ())
    if len(argument_items) != len(parameters):
        raise ValueResolutionError(
            f'La funcion {name} esperaba {len(parameters)} argumentos y '
            f'recibio {len(argument_items)}'
        )
    for parameter, argument in zip(parameters, argument_items):
        argument_info = infer_value(
            argument,
            namespace,
            functions,
            current_function=current_function,
        )
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
    member = _identifier_from_node(suffix)
    field = next((field for field in aggregate.fields if field.name == member), None)
    if field is None:
        raise ValueResolutionError(
            f'El miembro {member or "<anonimo>"} no existe en {aggregate.name}'
        )
    return ValueInfo(
        type_spec=field.type_spec,
        is_lvalue=True,
        identifier=value.identifier,
        address_origin=value.address_origin,
        storage_origin=value.storage_origin or value.address_origin,
        address_path=(*value.address_path, ('member', member)),
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
            return ValueInfo(
                type_spec=_address_type(operand.type_spec),
                address_origin=operand.storage_origin or operand.address_origin,
                address_of=operand.identifier,
                address_path=operand.address_path,
            )
        if operator in LOGICAL_NOT_OPERATORS:
            if not is_condition_type(operand.type_spec):
                raise ValueResolutionError(
                    'el operando de una negacion logica debe ser bool o entero escalar'
                )
            if operand.is_literal:
                return ValueInfo(
                    TypeSpec('bool'),
                    is_literal=True,
                    value=not bool(operand.value),
                )
            return ValueInfo(TypeSpec('bool'))

        if operand.type_spec.name != 'int' or operand.type_spec.pointer_level:
            raise ValueResolutionError(
                'el operando de una operacion unaria debe ser de tipo int'
            )
        if operator not in {'PLUS', 'MINUS'}:
            raise UnsupportedExpressionError(
                'solo se soportan signos unarios sobre enteros'
            )
        if operand.is_literal:
            value = operand.value if operator == 'PLUS' else -operand.value
            return ValueInfo(TypeSpec('int'), is_literal=True, value=value)
        return ValueInfo(TypeSpec('int'))

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

        if operator in COMPARISON_OPERATORS:
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
            both_bool = (
                left.type_spec.name == 'bool'
                and right.type_spec.name == 'bool'
            )
            if not ((left_is_integer and right_is_integer) or both_bool):
                raise ValueResolutionError(
                    'los operandos de una comparacion deben ser enteros o bool'
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
                    'los operandos logicos deben ser bool o enteros escalares'
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
                    left.type_spec,
                    is_literal=True,
                    value=value,
                )
            return ValueInfo(left.type_spec)

        if operator not in {'PLUS', 'MINUS', 'STAR', 'SLASH', 'PERCENT'}:
            raise UnsupportedExpressionError(
                'solo se soportan operaciones aritmeticas enteras en esta fase'
            )
        if left.type_spec != TypeSpec('int') or right.type_spec != TypeSpec('int'):
            raise ValueResolutionError(
                'los operandos de una operacion aritmetica deben ser de tipo int'
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
            return ValueInfo(TypeSpec('int'), is_literal=True, value=value)
        return ValueInfo(TypeSpec('int'))

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


def is_compatible(target: TypeSpec, source: ValueInfo) -> bool:
    source_type = source.type_spec

    if source_type.name == 'Null':
        return target.pointer_level > 0 and target.array_depth == 0

    if target.pointer_level > 0 and source.is_literal:
        return False

    if target.array_depth > 0:
        if (
            target.array_depth == 1
            and source.is_literal
            and source_type.name == 'chain'
            and target.name in {'char', 'byte'}
        ):
            data = _string_bytes(source.value, ascii_only=target.name == 'char')
            if data is None:
                return False
            declared_length = _target_array_length(target, 0)
            return declared_length is None or len(data) <= declared_length

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
                if source_length is not None and source_length > target_length:
                    return False
            elif source_length is not None and source_length != target_length:
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

    if source_type.array_depth > 0:
        return False

    if source.is_literal and source_type.name == 'chain' and target.name in {
        'char',
        'byte',
    }:
        data = _string_bytes(source.value, ascii_only=target.name == 'char')
        return data is not None and len(data) == 1

    if target.name == 'chain':
        return source_type.name == 'chain'

    if source.is_literal and source_type.name == 'int' and target.name in INTEGER_TYPES:
        if not isinstance(source.value, int) or isinstance(source.value, bool):
            return False
        bounds = _integer_bounds(target)
        return bounds is not None and bounds[0] <= source.value <= bounds[1]

    if source.is_literal and source_type.name in ('int', 'float'):
        if target.name in ('middle', 'float', 'double'):
            return True

    return _same_shape(target, source_type)

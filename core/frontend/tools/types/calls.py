from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from core.frontend.objects import AggregateSymbol, TypeSpec, ValueInfo, Variable
from gram import ast as gast

from .common import (
    INTEGER_TYPES, TypeResolutionError, ValueResolutionError,
    _children, _token, _token_kind, _token_value,
)
from .resolution import (
    _identifier_from_node, _namespace_owner, _resolve_aggregate,
    _resolve_function, _resolve_symbol, _unsafe_context, is_buffer_type,
)
from .compatibility import is_compatible


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
            parameter.is_length
            or parameter.is_size
            or parameter.is_region
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
    from .values import infer_value

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
    _validate_unique_arguments(name, parameters, argument_infos)
    return ValueInfo(TypeSpec(aggregate.name))


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
            or getattr(parameter, 'is_region', False)
            or getattr(parameter, 'is_receiver', False)
        )
    ]


def _validate_array_argument_storage(
    function_name: str,
    parameter: object,
    argument: ValueInfo,
) -> None:
    """Require addressable storage for arrays and borrowed buffers."""
    type_spec = getattr(parameter, 'type_spec', TypeSpec('void'))
    requires_storage = type_spec.array_depth or is_buffer_type(type_spec)
    if requires_storage and not argument.is_lvalue:
        raise ValueResolutionError(
            f'El argumento de {function_name} para {getattr(parameter, "name", "<array>")} '
            'debe ser una variable con almacenamiento propio'
        )


def _validate_unique_arguments(
    function_name: str,
    parameters: object,
    argument_infos: Mapping[str, ValueInfo],
) -> None:
    """Prove the non-overlap contract before allowing a ``unique`` call.

    Ordinary arrays and buffers retain Bagron's aliasing semantics. A call
    with ``unique`` must instead provide a known symbolic storage origin for
    every array/buffer argument that could overlap the exclusive region.
    """
    parameters = list(parameters)
    unique_parameters = [
        parameter for parameter in parameters
        if getattr(parameter, 'is_unique', False)
    ]
    if not unique_parameters:
        return

    data_parameters = [
        parameter for parameter in _visible_parameters(parameters)
        if (
            getattr(parameter.type_spec, 'array_depth', 0)
            or is_buffer_type(parameter.type_spec)
        )
    ]
    unique_origins: dict[str, str] = {}
    for parameter in data_parameters:
        argument = argument_infos.get(parameter.name)
        origin = getattr(argument, 'region_origin', None)
        if origin is None:
            raise ValueResolutionError(
                f'La llamada a {function_name} no puede demostrar la Region_t '
                f'de {parameter.name}; el origen debe ser almacenamiento local '
                'o un parametro unique'
            )
        if parameter.is_unique:
            previous = unique_origins.get(origin)
            if previous is not None:
                raise ValueResolutionError(
                    f'La llamada a {function_name} solapa las regiones unique '
                    f'{previous} y {parameter.name}'
                )
            unique_origins[origin] = parameter.name

    for parameter in data_parameters:
        if parameter.is_unique:
            continue
        origin = argument_infos[parameter.name].region_origin
        if origin in unique_origins:
            raise ValueResolutionError(
                f'La llamada a {function_name} pasa {parameter.name} dentro de '
                f'la Region_t unique de {unique_origins[origin]}'
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
        if is_size and source_type is not None and is_buffer_type(source_type):
            raise ValueResolutionError(
                f'Size_t de {function_name} no aplica al buffer {source_name}; '
                'un buffer siempre tiene elementos de un byte'
            )
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
        buffer_length = (
            source_type.array_lengths[0]
            if source_type is not None
            and is_buffer_type(source_type)
            and source_type.array_lengths
            else None
        )
        if is_length and is_buffer_type(source_type or TypeSpec('void')):
            if (
                buffer_length is None
                and not forwarded_expansion(source, is_length=True)
            ):
                raise ValueResolutionError(
                    f'Len_t de {function_name} requiere que {source_name} '
                    'sea un buffer con longitud conocida o un Len_t propagado'
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


def infer_call(
    node: object,
    namespace: Mapping[str, object] | Callable[[str], object | None],
    functions: Mapping[str, object] | Callable[[str], object | None] | None = None,
    *,
    current_function: object | None = None,
) -> ValueInfo:
    from .values import infer_value

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
        function = _resolve_function(
            functions,
            name or '',
            current_function=current_function,
        )
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
    _validate_unique_arguments(name, parameters, argument_infos)

    return_type = getattr(signature, 'return_type', TypeSpec('void'))
    return ValueInfo(
        return_type,
        address_origin='unknown' if return_type.pointer_level else None,
    )

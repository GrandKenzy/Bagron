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
    _buffer_index_value, _identifier_from_node, _resolve_aggregate,
    _resolve_function, _unsafe_context, _validate_array_index,
    is_buffer_type,
)
from .compatibility import _is_integer_scalar, is_compatible
from .calls import (
    _call_arguments, _infer_constructor_call, _resolve_method_call,
    _validate_array_argument_storage, _validate_expansion_parameters,
    _validate_unique_arguments,
    _visible_parameters,
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
        region_origin=value.region_origin,
        pointer_provenance_unknown=value.pointer_provenance_unknown,
        member_owner=value.member_owner,
    )


def _suffix_value(suffix: object) -> object | None:
    return next(
        (
            child for child in _children(suffix)
            if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
        ),
        None,
    )


def _infer_postfix(
    current: gast.ASTRef,
    namespace: Mapping[str, object] | Callable[[str], object | None],
    functions: Mapping[str, object] | Callable[[str], object | None] | None,
    current_function: object | None = None,
) -> ValueInfo:
    from .values import _member_value, infer_value

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
                        member_owner=result.member_owner,
                        region_origin=result.region_origin,
                    )
                elif is_buffer_type(result.type_spec):
                    result = _buffer_index_value(result, index)
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
                        member_owner=result.member_owner,
                        region_origin=result.region_origin,
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
                    member_owner=result.member_owner,
                    region_origin=result.region_origin,
                )
            elif is_buffer_type(result.type_spec):
                result = _buffer_index_value(result, index)
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
                    member_owner=result.member_owner,
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

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from core.frontend.objects import AggregateSymbol, TypeSpec, ValueInfo, Variable
from core.frontend.objects import OpaqueSymbol
from core.frontend.ownership import (
    CLOSED,
    DEAD,
    MAYBE_CLOSED,
    MAYBE_DEAD,
    MAYBE_MOVED,
    MOVED,
    is_opaque_symbol,
    state_for,
)
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
from .compatibility import (
    _integer_common_type,
    _integer_width,
    is_compatible,
    _wrap_unsigned_literal,
)
from .postfix import (
    _address_type, _deref_value, _infer_postfix, _unwrap_value,
)


def _affine_index_metadata(
    left: ValueInfo,
    right: ValueInfo,
    operator: str,
) -> tuple[str | None, int]:
    """Preserve ``index +/- literal`` metadata for safe array indexing."""
    if operator not in {'PLUS', 'MINUS'}:
        return None, 0
    if left.identifier is not None and right.is_literal and isinstance(right.value, int):
        offset = right.value if operator == 'PLUS' else -right.value
        return left.identifier, offset
    if operator == 'PLUS' and right.identifier is not None and left.is_literal:
        if isinstance(left.value, int):
            return right.identifier, left.value
    return None, 0
from .calls import _infer_magic_operator


def _aggregate_literal_fields(node: gast.ASTRef) -> tuple[str | None, list[object]]:
    """Return the declared type and direct designators of an aggregate literal."""
    type_name = next(
        (
            str(_token_value(child))
            for child in _children(node)
            if _token_kind(child) == 'IDENT'
        ),
        None,
    )
    fields: list[object] = []
    for child in _children(node):
        candidates = (
            child
            if isinstance(child, list)
            else _children(child)
            if not isinstance(child, gast.ASTRef)
            else (child,)
        )
        fields.extend(
            candidate
            for candidate in candidates
            if isinstance(candidate, gast.ASTRef)
            and candidate.name == 'DESIGNATED_FIELD'
        )
    return type_name, fields


def _aggregate_literal_value(
    node: gast.ASTRef,
    namespace: Mapping[str, object] | Callable[[str], object | None],
    functions: Mapping[str, object] | Callable[[str], object | None] | None,
    *,
    current_function: object | None,
) -> ValueInfo:
    type_name, designators = _aggregate_literal_fields(node)
    aggregate = _resolve_aggregate(namespace, type_name or '')
    if aggregate is None or aggregate.is_class:
        raise ValueResolutionError(
            f'{type_name or "<anonimo>"} no es un struct, mold o flags construible'
        )

    owner = _namespace_owner(namespace)
    resolver = getattr(owner, 'resolve_field', None)
    values: dict[str, ValueInfo] = {}
    for designator in designators:
        name = _identifier_from_node(designator)
        field = (
            resolver(type_name or aggregate.name, name)
            if callable(resolver)
            else next((item for item in aggregate.all_fields if item.name == name), None)
        )
        if field is None:
            raise ValueResolutionError(
                f'El campo {aggregate.name}.{name or "<anonimo>"} no existe'
            )
        if name in values:
            raise ValueResolutionError(
                f'El campo {aggregate.name}.{name} esta repetido en el literal'
            )
        value_node = next(
            (
                child for child in _children(designator)
                if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
            ),
            None,
        )
        if value_node is None:
            raise ValueResolutionError(
                f'El campo {aggregate.name}.{name} no tiene valor'
            )
        value = infer_value(
            value_node,
            namespace,
            functions,
            current_function=current_function,
        )
        if not is_compatible(field.type_spec, value):
            raise ValueResolutionError(
                f'El valor de {aggregate.name}.{name} no coincide con '
                f'{field.type_spec.canonical_name}'
            )
        values[name] = value

    if aggregate.kind == 'mold' and len(values) != 1:
        raise ValueResolutionError(
            f'El mold {aggregate.name} requiere exactamente un campo designado'
        )

    # Keep declaration order for constants and global emission.  Omitted
    # members are represented by an empty value of their concrete type; LLVM
    # lowers that form to the all-zero aggregate member without consulting a
    # flags declaration default.
    ordered = tuple(
        values.get(field.name, ValueInfo(field.type_spec, is_literal=True))
        for field in aggregate.all_fields
    )
    return ValueInfo(
        TypeSpec(type_name or aggregate.name, nominal_key=aggregate.registry_key),
        is_literal=all(value.is_literal for value in values.values()),
        value=tuple(values),
        items=ordered,
    )


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
            namespace_owner = getattr(namespace, '__self__', None)
            if (
                namespace_owner is not None
                and isinstance(
                    namespace_owner.resolve_type(operand.type_spec.name),
                    OpaqueSymbol,
                )
            ):
                raise ValueResolutionError(
                    'un descriptor opaque no puede convertirse en un puntero'
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
                buffer_derived=(
                    operand.buffer_derived
                    and operand.type_spec.pointer_level == 0
                ),
                member_owner=operand.member_owner,
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

        if operator == 'PLUS' and is_buffer_type(left.type_spec) and is_buffer_type(
            right.type_spec
        ):
            left_capacity = buffer_capacity(left.type_spec)
            right_capacity = buffer_capacity(right.type_spec)
            if left_capacity is None or right_capacity is None:
                raise ValueResolutionError(
                    'la concatenacion de buffer requiere capacidades conocidas '
                    'en compilacion'
                )
            capacity = left_capacity + right_capacity
            if capacity < 1:
                raise ValueResolutionError(
                    'la capacidad resultante de buffer es invalida'
                )
            return ValueInfo(
                TypeSpec('buffer', array_lengths=(capacity,)),
            )

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
            if operator in {'SHL', 'SHR'} and right.is_literal:
                width = _integer_width(result_type)
                if (
                    width is None
                    or not isinstance(right.value, int)
                    or right.value < 0
                    or right.value >= width
                ):
                    raise ValueResolutionError(
                        f'la cantidad de desplazamiento debe estar entre 0 y '
                        f'{(width or 0) - 1}'
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
                    value=_wrap_unsigned_literal(result_type, value),
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
            return ValueInfo(
                result_type,
                is_literal=True,
                value=_wrap_unsigned_literal(result_type, value),
            )
        range_base, range_offset = _affine_index_metadata(
            left,
            right,
            operator,
        )
        return ValueInfo(
            result_type,
            range_base=range_base,
            range_offset=range_offset,
        )

    if isinstance(current, gast.ASTRef) and current.name in ('POSTFIX_EXPR', 'MEMBER_ACCESS_TARGET'):
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

    if isinstance(current, gast.ASTRef) and current.name == 'AGGREGATE_VALUE':
        return _aggregate_literal_value(
            current,
            namespace,
            functions,
            current_function=current_function,
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
        resource_state = state_for(current_function, symbol)
        if resource_state == DEAD:
            raise ValueResolutionError(
                f'El buffer {value} esta dead; no puede usarse despues de Del'
            )
        if resource_state == MAYBE_DEAD:
            raise ValueResolutionError(
                f'El buffer {value} puede estar dead (esta dead en alguna '
                'ruta); no puede usarse despues de un Del condicional'
            )
        if resource_state == MAYBE_CLOSED and is_opaque_symbol(symbol):
            raise ValueResolutionError(
                f'El descriptor {value} puede estar closed en alguna ruta; no '
                'puede usarse despues de un close condicional'
            )
        if resource_state == MAYBE_MOVED and is_opaque_symbol(symbol):
            raise ValueResolutionError(
                f'El descriptor {value} puede estar moved en alguna ruta; no '
                'puede usarse despues de una transferencia condicional'
            )
        if resource_state == CLOSED and is_opaque_symbol(symbol):
            raise ValueResolutionError(
                f'El descriptor {value} esta closed; no puede usarse despues de close'
            )
        if resource_state == MOVED and is_opaque_symbol(symbol):
            raise ValueResolutionError(
                f'El descriptor {value} esta moved; no puede usarse despues de '
                'transferir su propiedad'
            )
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

        parameter_region = None
        is_borrowed_parameter = False
        signature = getattr(current_function, 'signature', None)
        for parameter in getattr(signature, 'parameters', ()):
            if parameter.name != str(value):
                continue
            if parameter.type_spec.array_depth or is_buffer_type(parameter.type_spec):
                is_borrowed_parameter = True
            if getattr(parameter, 'is_unique', False):
                parameter_region = (
                    f'parameter:{getattr(current_function, "name", "<function>")}:'
                    f'{parameter.name}'
                )
                break
        region_origin = parameter_region
        if region_origin is None and not is_borrowed_parameter and (
            symbol.type_spec.array_depth or is_buffer_type(symbol.type_spec)
        ):
            # ``id(symbol)`` is stable for this compilation and distinguishes
            # two locals that otherwise share the same ``scope_kind``.
            region_origin = f'symbol:{id(symbol)}'

        return ValueInfo(
            type_spec=symbol.type_spec,
            identifier=str(value),
            value=(initialized.value if constant_literal else symbol.value),
            items=(getattr(initialized, 'items', ()) if initialized is not None else ()),
            is_literal=constant_literal,
            is_lvalue=True,
            address_origin=(
                pointer_origin
                if symbol.type_spec.pointer_level
                else getattr(symbol, 'scope_kind', None)
            ),
            storage_origin=getattr(symbol, 'scope_kind', None),
            address_path=(),
            member_owner=(
                getattr(initialized, 'member_owner', None)
                if initialized is not None
                else None
            ),
            known_index_source=getattr(symbol, 'for_array_source', None),
            known_index_path=getattr(symbol, 'for_array_path', ()),
            known_index_length=getattr(symbol, 'for_array_length', None),
            region_origin=region_origin,
            buffer_derived=(
                getattr(initialized, 'buffer_derived', False)
                if initialized is not None
                else False
            ),
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

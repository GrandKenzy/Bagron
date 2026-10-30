from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from core.frontend.handles import VariableHandle, handle_variable
from core.frontend.objects import TypeSpec, ValueInfo, Variable
from core.frontend.tools.types import (
    TypeResolutionError,
    UnsupportedExpressionError,
    ValueResolutionError,
    buffer_capacity,
    constant_chain_value,
    infer_value,
    is_buffer_type,
    is_compatible,
    resolve_type,
)
from core.storage import Storage
from gram import ast as gast

if TYPE_CHECKING:
    from core.compiler import Compiler


def _bare_identifier(node: object) -> str | None:
    if isinstance(node, gast.ASTRef):
        if node.name in ('VALUE', 'POSTFIX_EXPR', 'PRIMARY') and len(node.nodes) == 1:
            return _bare_identifier(node.nodes[0])
        return None

    token = getattr(node, 'token', None)
    token_kind = getattr(getattr(token, 'token', None), 'name', None)
    if token_kind == 'IDENT':
        return str(getattr(token, 'value', ''))

    return None


def _is_buffer_concat(node: object) -> bool:
    current = node
    while isinstance(current, gast.ASTRef):
        if current.name in ('VALUE', 'POSTFIX_EXPR', 'PRIMARY') and len(current.nodes) == 1:
            current = current.nodes[0]
            continue
        if current.name == 'PAREN_VALUE':
            inner = next(
                (
                    child for child in current.nodes
                    if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
                ),
                None,
            )
            if inner is None:
                return False
            current = inner
            continue
        break
    if type(current).__name__ != 'ASTBinaryOp':
        return False
    operator = getattr(getattr(current.operator, 'token', None), 'name', None)
    return operator == 'PLUS'


def build_symbol(
    storage,
    name: str,
    type_spec: TypeSpec,
    value_node: object | None = None,
    kind: str = 'local',
    privacy: str = 'public',
) -> Variable:
    immutable = type_spec.value_is_const or type_spec.name == 'chain'
    symbol = Variable(
        name,
        type_spec.canonical_name,
        type_spec.pointer_level,
        value_node,
    )
    symbol.type_spec = type_spec
    symbol.type = type_spec.canonical_name
    symbol.is_const = immutable
    symbol.value_is_const = immutable
    symbol.pointer_is_const = type_spec.pointer_is_const
    symbol.pointer_size = (
        storage.pointer_size
        if type_spec.pointer_level > 0
        else None
    )
    symbol.privacy = privacy
    symbol.scope_kind = kind
    symbol.initialized = kind == 'parameter' or value_node is not None
    symbol.bit_width = type_spec.bit_width
    symbol.signed = type_spec.signed
    return symbol


def _validate_callptr(
    compiler: Compiler,
    storage,
    handle: VariableHandle,
    symbol: Variable,
) -> None:
    if symbol.pointer_level == 0:
        compiler.error(
            f'El tipo callptr requiere al menos un nivel de puntero: {handle.name}'
        )
        return

    if handle.value_node is None:
        return

    target_name = _bare_identifier(handle.value_node)
    function = compiler.function_lookup.get(target_name) if target_name else None
    source = compiler.storage.namespace.get(target_name) if target_name else None

    if function is not None:
        symbol.call_signature = function.signature
    elif source is not None and getattr(source, 'call_signature', None) is not None:
        symbol.call_signature = source.call_signature
    else:
        compiler.error(
            f'El inicializador de {handle.name} debe ser una función o un callptr compatible'
        )


def _frontend_initializer_value(
    storage,
    symbol: Variable,
    value_node: object,
    functions,
    *,
    current_function: object | None = None,
) -> tuple[object, bool]:
    """Resolve an implicit class conversion and report whether it was used."""
    source_info = infer_value(
        value_node,
        storage.resolve,
        functions,
        current_function=current_function,
    )
    if is_compatible(symbol.type_spec, source_info):
        return source_info, False

    aggregate = storage.resolve_type(symbol.type_spec.name)
    parameters = getattr(aggregate, 'constructor_parameters', None)
    initializer_name = getattr(aggregate, 'initializer_name', None)
    visible_parameters = [
        parameter for parameter in (parameters or ())
        if not (
            getattr(parameter, 'is_length', False)
            or getattr(parameter, 'is_size', False)
            or getattr(parameter, 'is_region', False)
        )
    ]
    if initializer_name != '__frontend__' or len(visible_parameters) != 1:
        return source_info, False

    parameter = visible_parameters[0]
    if not is_compatible(parameter.type_spec, source_info):
        raise ValueResolutionError(
            f'La conversion frontend de {symbol.type_spec.name} no acepta '
            f'{source_info.type_spec.canonical_name}; esperaba '
            f'{parameter.type_spec.canonical_name}'
        )

    # Preserve field constants for global aggregate initializers.  Local
    # declarations use the original AST in the LLVM emitter, so a dynamic
    # source remains valid there even when this value is not literal.
    context = Storage(
        storage.root,
        parent=storage,
        scope_name=f'frontend:{symbol.type_spec.name}',
    )
    parameter_symbol = build_symbol(
        context,
        parameter.name,
        parameter.type_spec,
        kind='parameter',
    )
    parameter_symbol.value_info = source_info
    parameter_symbol.value_is_const = source_info.is_literal
    context.add(parameter.name, parameter_symbol)

    def collect_fields(
        current_aggregate,
        current_context,
    ) -> list[ValueInfo] | None:
        parent_name = getattr(current_aggregate, 'parent_type', None)
        parent = (
            storage.resolve_type(parent_name)
            if parent_name
            else None
        )
        values: list[ValueInfo] = []
        if parent is not None and getattr(parent, 'initializer_name', None):
            parameters = [
                parameter for parameter in (
                    getattr(parent, 'constructor_parameters', None) or ()
                )
                if not (
                    getattr(parameter, 'is_length', False)
                    or getattr(parameter, 'is_size', False)
                    or getattr(parameter, 'is_region', False)
                    or getattr(parameter, 'is_receiver', False)
                )
            ]
            arguments = getattr(
                current_aggregate,
                'parent_initializer_arguments',
                (),
            )
            parent_context = Storage(
                storage.root,
                parent=current_context,
                scope_name=f'frontend:{parent.name}',
            )
            for parameter, argument in zip(parameters, arguments):
                try:
                    argument_info = infer_value(
                        argument,
                        current_context.resolve,
                        functions,
                        current_function=current_function,
                    )
                except (UnsupportedExpressionError, ValueResolutionError):
                    return None
                parameter_symbol = build_symbol(
                    parent_context,
                    parameter.name,
                    parameter.type_spec,
                    kind='parameter',
                )
                parameter_symbol.value_info = argument_info
                parameter_symbol.value_is_const = argument_info.is_literal
                parent_context.add(parameter.name, parameter_symbol)

            parent_values = collect_fields(parent, parent_context)
            if parent_values is None:
                return None
            values.extend(parent_values)

        for field in getattr(current_aggregate, 'fields', ()):
            initializer = getattr(field, 'initializer_node', None)
            if initializer is None:
                values.append(ValueInfo(field.type_spec))
                continue
            try:
                field_value = infer_value(
                    initializer,
                    current_context.resolve,
                    functions,
                    current_function=current_function,
                )
            except (UnsupportedExpressionError, ValueResolutionError):
                return None
            values.append(field_value)
        return values

    field_values = collect_fields(aggregate, context) or []

    return ValueInfo(
        symbol.type_spec,
        is_literal=all(
            field_value.is_literal for field_value in field_values
        ),
        value=tuple(field_values),
        items=tuple(field_values),
    ), True


def _validate_initializer(
    compiler: Compiler,
    storage,
    handle: VariableHandle,
    symbol: Variable,
    *,
    current_function: object | None = None,
) -> None:
    if handle.value_node is None:
        return

    if symbol.type_spec.name == 'callptr':
        _validate_callptr(compiler, storage, handle, symbol)
        return

    try:
        aggregate = storage.resolve_type(symbol.type_spec.name)
        if (
            symbol.type_spec.pointer_level == 0
            and symbol.type_spec.array_depth == 0
            and getattr(aggregate, 'initializer_name', None) == '__frontend__'
        ):
            value_info, uses_frontend = _frontend_initializer_value(
                storage,
                symbol,
                handle.value_node,
                compiler.function_lookup,
                current_function=current_function,
            )
            if uses_frontend:
                symbol.value_info = value_info
                symbol.uses_frontend_initializer = True
                return

        value_info = infer_value(
            handle.value_node,
            storage.resolve,
            compiler.function_lookup,
            current_function=current_function,
        )
    except UnsupportedExpressionError as error:
        if symbol.scope_kind == 'global':
            compiler.error(f'{handle.name}: {error}')
        return
    except ValueResolutionError as error:
        compiler.error(f'{handle.name}: {error}')
        return

    if is_buffer_type(symbol.type_spec) and buffer_capacity(symbol.type_spec) is None:
        inferred_capacity = None
        if is_buffer_type(value_info.type_spec):
            inferred_capacity = buffer_capacity(value_info.type_spec)
        elif (
            value_info.is_literal
            and value_info.type_spec.array_depth == 1
            and value_info.items
        ):
            inferred_capacity = len(value_info.items)
        max_capacity = (1 << (compiler.storage.pointer_size * 8)) - 1
        if (
            inferred_capacity is None
            or inferred_capacity < 1
            or inferred_capacity > max_capacity
        ):
            compiler.error(
                f'{handle.name}: buffer[] requiere un inicializador con '
                'capacidad conocida que quepa en usize'
            )
            return
        symbol.type_spec = replace(
            symbol.type_spec,
            array_lengths=(inferred_capacity,),
        )
        symbol.type = symbol.type_spec.canonical_name

    if (
        is_buffer_type(value_info.type_spec)
        and not _is_buffer_concat(handle.value_node)
    ):
        compiler.error(
            f'{handle.name}: la propiedad de buffer entre asignaciones y '
            'funciones aun no esta definida; usa una concatenacion'
        )
        return

    if not is_compatible(symbol.type_spec, value_info):
        compiler.error(
            f'El valor inicial de {handle.name} no coincide con '
            f'{symbol.type_spec.canonical_name}'
        )
        return

    if symbol.type_spec.name == 'chain' and value_info.type_spec.name != 'chain':
        converted = constant_chain_value(value_info)
        if converted is None:
            compiler.error(
                f'El valor inicial de {handle.name} requiere un char constante'
            )
            return
        value_info = converted

    symbol.value_info = value_info

    if symbol.type_spec.array_depth:
        lengths = list(symbol.type_spec.array_lengths)
        source_type = value_info.type_spec
        if (
            symbol.type_spec.array_depth == 1
            and source_type.name == 'chain'
            and symbol.type_spec.name in {'char', 'byte'}
            and isinstance(value_info.value, str)
        ):
            try:
                encoded = value_info.value.encode(
                    'ascii' if symbol.type_spec.name == 'char' else 'utf-8'
                )
            except UnicodeEncodeError:
                encoded = None
            if encoded is not None and lengths[0] is None:
                lengths[0] = (
                    len(encoded) + 1
                    if symbol.type_spec.name == 'char'
                    else len(encoded)
                )
        elif source_type.array_depth == symbol.type_spec.array_depth:
            for index, length in enumerate(source_type.array_lengths):
                if index < len(lengths) and lengths[index] is None:
                    if (
                        symbol.type_spec.name == 'char'
                        and symbol.type_spec.array_depth == 1
                        and index == 0
                    ):
                        lengths[index] = length + 1
                    else:
                        lengths[index] = length

        if tuple(lengths) != symbol.type_spec.array_lengths:
            symbol.type_spec = replace(
                symbol.type_spec,
                array_lengths=tuple(lengths),
            )
            symbol.type = symbol.type_spec.canonical_name


def collect_in_scope(
    compiler: Compiler,
    storage,
    node: gast.ASTRef,
    kind: str = 'local',
    *,
    validate: bool = True,
    current_function: object | None = None,
) -> Variable | None:
    """Collect and validate one variable in the selected lexical scope."""
    handle = handle_variable(node)
    if handle is None:
        return None

    if storage.contains_local(handle.name):
        compiler.error(
            f'La variable {handle.name} ya fue declarada en el scope '
            f'{storage.scope_name}'
        )
        return None

    try:
        type_spec = resolve_type(
            handle.type_node,
            pointer_level=handle.pointer_level,
            pointer_is_const=handle.pointer_is_const,
            pointer_size=compiler.storage.pointer_size,
        )
    except TypeResolutionError as error:
        compiler.error(f'{handle.name}: {error}')
        return None

    if type_spec.name == 'Never':
        compiler.error(
            f'La variable {handle.name} no puede usar Never como almacenamiento'
        )
        return None

    if is_buffer_type(type_spec) and kind == 'global':
        compiler.error(
            f'El buffer global {handle.name} aun no tiene inicializacion '
            'dinamica de modulo; declaralo dentro de una funcion'
        )
        return None

    if type_spec.name == 'void' and type_spec.pointer_level == 0:
        compiler.error(
            f'La variable {handle.name} no puede usar void como almacenamiento'
        )
        return None

    symbol = build_symbol(
        storage,
        handle.name,
        type_spec,
        handle.value_node,
        kind=kind,
        privacy=handle.privacy,
    )
    if kind == 'global':
        symbol.module_path = compiler.module_for_node(node)
    # Scalars must make their initialization point explicit. Fixed-size
    # arrays and named aggregates already receive deterministic static
    # zero/storage initialization, so declarations such as a matrix that is
    # populated element by element remain valid without a synthetic literal.
    aggregate = storage.resolve_type(type_spec.name)
    initializer_name = getattr(aggregate, 'initializer_name', None)
    requires_constructor = (
        type_spec.pointer_level == 0
        and type_spec.array_depth == 0
        and getattr(aggregate, 'constructor_parameters', None) is not None
    )
    implicit_zero_storage = (
        type_spec.array_depth > 0
        or storage.resolve_type(type_spec.name) is not None
    )
    if handle.value_node is None and requires_constructor:
        if initializer_name == '__frontend__':
            compiler.error(
                f'La instancia {handle.name} de {type_spec.name} requiere un '
                'valor compatible con __frontend__'
            )
        else:
            compiler.error(
                f'La instancia {handle.name} de {type_spec.name} requiere una '
                f'llamada a {type_spec.name}(...)'
            )
    elif kind == 'local' and handle.value_node is None and not implicit_zero_storage:
        compiler.error(
            f'La variable local {handle.name} debe tener un inicializador; '
            'las variables locales se inicializan al declararse'
        )
    if (
        type_spec.array_depth
        and handle.value_node is None
        and any(length is None for length in type_spec.array_lengths)
    ):
        compiler.error(
            f'El array {handle.name} requiere un inicializador para inferir su tamano'
        )
    if (
        is_buffer_type(type_spec)
        and buffer_capacity(type_spec) is None
        and handle.value_node is None
    ):
        compiler.error(
            f'El buffer {handle.name} requiere un inicializador para inferir '
            'su capacidad'
        )
    if type_spec.name == 'chain' and handle.value_node is None:
        compiler.error(f'El chain {handle.name} debe tener un inicializador')
    if validate:
        _validate_initializer(
            compiler,
            storage,
            handle,
            symbol,
            current_function=current_function,
        )
    storage.add(handle.name, symbol)
    return symbol


def collect_global(
    compiler: Compiler,
    node: gast.ASTRef,
    *,
    validate: bool = True,
) -> Variable | None:
    """Collect and validate one top-level global variable declaration."""
    return collect_in_scope(
        compiler,
        compiler.storage,
        node,
        kind='global',
        validate=validate,
    )


def validate_initializer(
    compiler: Compiler,
    storage,
    handle: VariableHandle,
    symbol: Variable,
    *,
    current_function: object | None = None,
) -> None:
    """Validate an initializer after all globals have been registered."""
    _validate_initializer(
        compiler,
        storage,
        handle,
        symbol,
        current_function=current_function,
    )


def collect_local(
    compiler: Compiler,
    storage,
    node: gast.ASTRef,
    *,
    current_function: object | None = None,
) -> Variable | None:
    return collect_in_scope(
        compiler,
        storage,
        node,
        kind='local',
        current_function=current_function,
    )


__all__ = [
    'build_symbol',
    'collect_global',
    'collect_in_scope',
    'collect_local',
    'validate_initializer',
]

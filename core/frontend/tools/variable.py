from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from core.frontend.handles import VariableHandle, handle_variable
from core.frontend.objects import TypeSpec, Variable
from core.frontend.tools.types import (
    TypeResolutionError,
    UnsupportedExpressionError,
    ValueResolutionError,
    constant_chain_value,
    infer_value,
    is_compatible,
    resolve_type,
)
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
    function = compiler.storage.functions.get(target_name) if target_name else None
    source = compiler.storage.namespace.get(target_name) if target_name else None

    if function is not None:
        symbol.call_signature = function.signature
    elif source is not None and getattr(source, 'call_signature', None) is not None:
        symbol.call_signature = source.call_signature
    else:
        compiler.error(
            f'El inicializador de {handle.name} debe ser una función o un callptr compatible'
        )


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
        value_info = infer_value(
            handle.value_node,
            storage.resolve,
            compiler.storage.functions,
            current_function=current_function,
        )
    except UnsupportedExpressionError as error:
        if symbol.scope_kind == 'global':
            compiler.error(f'{handle.name}: {error}')
        return
    except ValueResolutionError as error:
        compiler.error(f'{handle.name}: {error}')
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
    if (
        type_spec.array_depth
        and handle.value_node is None
        and any(length is None for length in type_spec.array_lengths)
    ):
        compiler.error(
            f'El array {handle.name} requiere un inicializador para inferir su tamano'
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

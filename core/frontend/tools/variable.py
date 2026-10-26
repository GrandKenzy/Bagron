from __future__ import annotations

from typing import TYPE_CHECKING

from core.frontend.handles import VariableHandle, handle_variable
from core.frontend.objects import TypeSpec, Variable
from core.frontend.tools.types import (
    TypeResolutionError,
    UnsupportedExpressionError,
    ValueResolutionError,
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
    symbol = Variable(
        name,
        type_spec.canonical_name,
        type_spec.pointer_level,
        value_node,
    )
    symbol.type_spec = type_spec
    symbol.type = type_spec.canonical_name
    symbol.is_const = type_spec.value_is_const
    symbol.value_is_const = type_spec.value_is_const
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
) -> None:
    if handle.value_node is None:
        return

    if symbol.type_spec.name == 'callptr':
        _validate_callptr(compiler, storage, handle, symbol)
        return

    try:
        value_info = infer_value(handle.value_node, storage.resolve)
    except UnsupportedExpressionError as error:
        if symbol.scope_kind == 'global':
            compiler.error(f'{handle.name}: {error}')
        return
    except ValueResolutionError as error:
        compiler.error(f'{handle.name}: {error}')
        return

    symbol.value_info = value_info
    if not is_compatible(symbol.type_spec, value_info):
        compiler.error(
            f'El valor inicial de {handle.name} no coincide con '
            f'{symbol.type_spec.canonical_name}'
        )


def collect_in_scope(
    compiler: Compiler,
    storage,
    node: gast.ASTRef,
    kind: str = 'local',
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
        )
    except TypeResolutionError as error:
        compiler.error(f'{handle.name}: {error}')
        return None

    symbol = build_symbol(
        storage,
        handle.name,
        type_spec,
        handle.value_node,
        kind=kind,
        privacy=handle.privacy,
    )
    _validate_initializer(compiler, storage, handle, symbol)
    storage.add(handle.name, symbol)
    return symbol


def collect_global(compiler: Compiler, node: gast.ASTRef) -> Variable | None:
    """Collect and validate one top-level global variable declaration."""
    return collect_in_scope(compiler, compiler.storage, node, kind='global')


def collect_local(compiler: Compiler, storage, node: gast.ASTRef) -> Variable | None:
    return collect_in_scope(compiler, storage, node, kind='local')


__all__ = ['build_symbol', 'collect_global', 'collect_in_scope', 'collect_local']

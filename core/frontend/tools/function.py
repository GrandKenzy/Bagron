from __future__ import annotations

from typing import TYPE_CHECKING

from core.frontend.objects import (
    FunctionSignature,
    FunctionSymbol,
    ParameterSpec,
    TypeSpec,
)
from core.frontend.tools.types import (
    TypeResolutionError,
    UnsupportedExpressionError,
    ValueResolutionError,
    infer_value,
    is_compatible,
    resolve_type,
)
from core.frontend.tools.variable import build_symbol, collect_local
from gram import ast as gast

if TYPE_CHECKING:
    from core.compiler import Compiler


def _children(node: object) -> list[object]:
    if isinstance(node, list):
        return list(node)

    items = getattr(node, 'items', None)
    if items is not None:
        return list(items)

    nodes = getattr(node, 'nodes', None)
    if nodes is not None:
        return list(nodes)

    return []


def _token(node: object) -> object | None:
    return getattr(node, 'token', None)


def _token_kind(node: object) -> str | None:
    token = _token(node)
    token = getattr(token, 'token', token)
    return getattr(token, 'name', None)


def _token_value(node: object) -> object | None:
    token = _token(node)
    return getattr(token, 'value', None)


def _identifier(node: object) -> str | None:
    if _token_kind(node) == 'IDENT':
        return str(_token_value(node))

    for child in _children(node):
        found = _identifier(child)
        if found is not None:
            return found

    return None


def _declarator_info(node: gast.ASTRef) -> tuple[str, int, bool]:
    name = ''
    pointer_level = 0
    pointer_is_const = False

    for child in node.nodes:
        if isinstance(child, gast.ASTKeyword):
            pointer_is_const = child.token.value == 'const'
        elif isinstance(child, gast.ASTRef) and child.name == 'POINTER':
            pointer_level = len(child.nodes)
        elif _token_kind(child) == 'IDENT':
            name = str(_token_value(child))

    return name, pointer_level, pointer_is_const


def _signature_node(node: gast.ASTRef) -> gast.ASTRef | None:
    return next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef)
            and child.name == 'FUNCTION_SIGNATURE'
        ),
        None,
    )


def _body_node(node: gast.ASTRef) -> gast.ASTRef | None:
    return next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef)
            and child.name == 'FUNCTION_BODY'
        ),
        None,
    )


def _parameter_items(parameters: gast.ASTRef) -> list[object]:
    if not parameters.nodes:
        return []
    return _children(parameters.nodes[0])


def _parameter_spec(pair: gast.ASTRef) -> ParameterSpec:
    declarator = pair.nodes[0]
    type_node = pair.nodes[2]
    name, pointer_level, pointer_is_const = _declarator_info(declarator)
    type_spec = resolve_type(
        type_node,
        pointer_level=pointer_level,
        pointer_is_const=pointer_is_const,
    )
    return ParameterSpec(
        name=name,
        type_spec=type_spec,
        has_default=len(pair.nodes) > 3,
    )


def signature_from_node(node: gast.ASTRef) -> tuple[str, FunctionSignature]:
    signature = _signature_node(node)
    if signature is None:
        raise TypeResolutionError('La funcion no contiene una firma valida')

    children = _children(signature)
    name = _identifier(signature) or ''
    parameter_index = next(
        (
            index for index, child in enumerate(children)
            if isinstance(child, gast.ASTRef)
            and child.name == 'PARAMETERS'
        ),
        None,
    )
    if parameter_index is None or parameter_index + 1 >= len(children):
        raise TypeResolutionError(f'La firma de {name or "<anonima>"} es invalida')

    parameters_node = children[parameter_index]
    parameters = tuple(
        _parameter_spec(pair)
        for pair in _parameter_items(parameters_node)
        if isinstance(pair, gast.ASTRef) and pair.name == 'PAIR_PARAM'
    )

    return_node = children[parameter_index + 1]
    return_pointer = 0
    for child in children[parameter_index + 2:]:
        if isinstance(child, gast.ASTRef) and child.name == 'POINTER':
            return_pointer = len(child.nodes)
            break

    return name, FunctionSignature(
        parameters=parameters,
        return_type=resolve_type(return_node, pointer_level=return_pointer),
    )


def _validate_bit_width(compiler: Compiler, name: str, type_spec: TypeSpec) -> None:
    if type_spec.bit_width is not None and type_spec.bit_width < 1:
        compiler.error(
            f'El ancho de {type_spec.canonical_name} debe ser mayor que cero: {name}'
        )


def _bind_parameters(compiler: Compiler, symbol: FunctionSymbol) -> None:
    scope = symbol.scope
    if scope is None:
        return

    for parameter in symbol.signature.parameters:
        if parameter.has_default:
            compiler.error(
                f'El parametro {parameter.name} de {symbol.name} no puede tener '
                'valor por defecto en esta fase'
            )

        _validate_bit_width(compiler, parameter.name, parameter.type_spec)
        if not parameter.name:
            compiler.error(f'La funcion {symbol.name} contiene un parametro sin nombre')
            continue
        if scope.contains_local(parameter.name):
            compiler.error(
                f'El parametro {parameter.name} esta duplicado en la funcion '
                f'{symbol.name}'
            )
            continue

        variable = build_symbol(
            scope,
            parameter.name,
            parameter.type_spec,
            kind='parameter',
        )
        scope.add(parameter.name, variable)


def collect(compiler: Compiler, nodes: list[gast.ASTRef]) -> None:
    """Register only top-level function signatures and parameter scopes."""
    for node in nodes:
        if node.name != 'FUNCTION':
            continue

        try:
            name, signature = signature_from_node(node)
        except TypeResolutionError as error:
            compiler.error(str(error))
            continue

        if not name:
            compiler.error('La funcion no tiene nombre')
            continue
        if name in compiler.storage.functions:
            compiler.error(f'La funcion ya fue declarada: {name}')
            continue

        symbol = FunctionSymbol(name, signature)
        compiler.storage.define_function(symbol)
        compiler.function_bindings[id(node)] = symbol
        _validate_bit_width(compiler, name, signature.return_type)
        _bind_parameters(compiler, symbol)


def _return_value(node: gast.ASTRef) -> object | None:
    return next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
        ),
        None,
    )


def _validate_return(compiler: Compiler, symbol: FunctionSymbol, node: gast.ASTRef) -> None:
    scope = symbol.scope
    if scope is None:
        return

    value_node = _return_value(node)
    return_type = symbol.signature.return_type

    if return_type.name == 'void':
        if value_node is not None:
            compiler.error(f'La funcion {symbol.name} no puede retornar un valor')
        return

    if value_node is None:
        compiler.error(f'La funcion {symbol.name} debe retornar un valor')
        return

    try:
        value_info = infer_value(value_node, scope.resolve)
    except UnsupportedExpressionError:
        return
    except ValueResolutionError as error:
        compiler.error(f'{symbol.name}: {error}')
        return

    if not is_compatible(return_type, value_info):
        compiler.error(
            f'El return de {symbol.name} no coincide con '
            f'{return_type.canonical_name}'
        )
        return

    symbol.return_values.append(value_info)


def _for_binding(compiler: Compiler, symbol: FunctionSymbol, node: gast.ASTRef) -> None:
    scope = symbol.scope
    if scope is None:
        return

    signature = next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef) and child.name == 'FOR_SIGNATURE'
        ),
        None,
    )
    if signature is None:
        return

    children = _children(signature)
    name = ''
    type_node = None
    for index, child in enumerate(children):
        if _token_kind(child) == 'IDENT' and not name:
            name = str(_token_value(child))
        if _token_value(child) == ':':
            if index + 1 < len(children):
                type_node = children[index + 1]
            break

    if not name or type_node is None:
        return

    try:
        type_spec = resolve_type(type_node)
    except TypeResolutionError as error:
        compiler.error(f'{name}: {error}')
        return

    if scope.contains_local(name):
        compiler.error(
            f'La variable {name} ya fue declarada en el scope {scope.scope_name}'
        )
        return

    scope.add(name, build_symbol(scope, name, type_spec, kind='local'))


_DEFINITION_NODES = {'CLASS', 'ENUM', 'FLAGS', 'MOLD', 'STRUCT', 'FUNCTION'}


def _process_body_node(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: object,
    returns: list[int],
) -> None:
    if isinstance(node, gast.ASTKeyword):
        if node.token.value == 'pass':
            symbol.body_supported_for_entrypoint = False
        return
    if isinstance(node, list):
        for child in node:
            _process_body_node(compiler, symbol, child, returns)
        return
    if not isinstance(node, gast.ASTRef):
        return

    if node.name in _DEFINITION_NODES:
        return
    if node.name == 'VAR':
        symbol.body_supported_for_entrypoint = False
        if symbol.scope is not None:
            collect_local(compiler, symbol.scope, node)
        return
    if node.name == 'RETURN':
        _validate_return(compiler, symbol, node)
        returns[0] += 1
        return
    if node.name == 'FOR':
        symbol.body_supported_for_entrypoint = False
        _for_binding(compiler, symbol, node)

    if node.name in {'CALL', 'IF', 'WHILE', 'VAR_ASSIGNATION'}:
        symbol.body_supported_for_entrypoint = False

    for child in _children(node):
        _process_body_node(compiler, symbol, child, returns)


def process(compiler: Compiler, node: gast.ASTRef) -> None:
    """Collect local variables and validate returns for one top-level function."""
    symbol = compiler.function_bindings.get(id(node))
    if symbol is None:
        return

    body = _body_node(node)
    if body is None:
        compiler.error(f'La funcion {symbol.name} no tiene cuerpo')
        return

    returns = [0]
    for child in _children(body):
        _process_body_node(compiler, symbol, child, returns)

    if symbol.signature.return_type.name != 'void' and returns[0] == 0:
        compiler.error(f'La funcion {symbol.name} no tiene return')


__all__ = ['collect', 'process', 'signature_from_node']

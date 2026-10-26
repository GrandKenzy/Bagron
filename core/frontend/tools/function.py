from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterable

from core.frontend.objects import FunctionSignature, FunctionSymbol, TypeInfo

if TYPE_CHECKING:
    from core.compiler import Compiler
from gram import ast as gast


def _children(node: object) -> list[object]:
    if isinstance(node, list):
        return node

    items = getattr(node, 'items', None)
    if items is not None:
        return list(items)

    nodes = getattr(node, 'nodes', None)
    if nodes is not None:
        return list(nodes)

    return []


def _token_kind(node: object) -> str | None:
    token = getattr(node, 'token', None)
    token = getattr(token, 'token', token)
    return getattr(token, 'name', None)


def _identifier(node: object) -> str | None:
    if _token_kind(node) == 'IDENT':
        token = getattr(node, 'token')
        return str(getattr(token, 'value', ''))

    for child in _children(node):
        found = _identifier(child)
        if found is not None:
            return found

    return None


def _type_is_const(node: object) -> bool:
    token = getattr(node, 'token', None)
    if token is not None and getattr(token, 'value', None) == 'const':
        return True

    return any(_type_is_const(child) for child in _children(node))


def _type_name(node: object) -> str:
    token = getattr(node, 'token', None)
    if token is not None:
        value = str(getattr(token, 'value', ''))
        return '' if value == 'const' else value

    return ''.join(_type_name(child) for child in _children(node))


def _bitint_info(type_name: str) -> tuple[int, bool] | None:
    match = re.fullmatch(r'(u?Bint)<(\d+)>(?:\[\])*', type_name)
    if match is None:
        return None
    return int(match.group(2)), match.group(1) == 'Bint'


def _pointer_level(node: object) -> int:
    if isinstance(node, gast.ASTRef) and node.name == 'POINTER':
        return len(node.nodes)

    return 0


def _declarator_info(node: gast.ASTRef) -> tuple[str, int]:
    name = _identifier(node) or ''
    pointer_level = 0

    for child in node.nodes:
        if isinstance(child, gast.ASTRef):
            pointer_level = max(pointer_level, _pointer_level(child))

    return name, pointer_level


def _type_info(node: object, pointer_level: int = 0) -> TypeInfo:
    name = _type_name(node)
    bitint = _bitint_info(name)
    return TypeInfo(
        name=name,
        pointer_level=pointer_level,
        value_is_const=_type_is_const(node),
        bit_width=bitint[0] if bitint else None,
        signed=bitint[1] if bitint else None,
    )


def _parameter_signature(pair: gast.ASTRef) -> TypeInfo:
    declarator = pair.nodes[0]
    type_node = pair.nodes[2]
    _, pointer_level = _declarator_info(declarator)
    return _type_info(type_node, pointer_level)


def signature_from_node(node: gast.ASTRef) -> tuple[str, FunctionSignature]:
    signature = node.nodes[0]
    children = signature.nodes
    name = _identifier(signature) or ''

    parameter_index = next(
        index
        for index, child in enumerate(children)
        if isinstance(child, gast.ASTRef) and child.name == 'PARAMETERS'
    )
    parameters_node = children[parameter_index]
    parameter_items = (
        _children(parameters_node.nodes[0])
        if parameters_node.nodes
        else []
    )
    parameters = tuple(
        _parameter_signature(pair)
        for pair in parameter_items
        if isinstance(pair, gast.ASTRef) and pair.name == 'PAIR_PARAM'
    )

    return_node = children[parameter_index + 1]
    return_pointer = 0
    if len(children) > parameter_index + 2:
        return_pointer = _pointer_level(children[parameter_index + 2])

    return name, FunctionSignature(
        parameters=parameters,
        return_type=_type_info(return_node, return_pointer),
    )


def _walk(nodes: Iterable[object]):
    for node in nodes:
        if isinstance(node, gast.ASTRef):
            yield node
            yield from _walk(node.nodes)
        elif isinstance(node, list):
            yield from _walk(node)
        else:
            items = getattr(node, 'items', None)
            if items is not None:
                yield from _walk(items)


def collect(compiler: Compiler, nodes: list[gast.ASTRef]):
    for node in _walk(nodes):
        if node.name != 'FUNCTION':
            continue

        name, signature = signature_from_node(node)
        if name:
            for type_info in (*signature.parameters, signature.return_type):
                if type_info.bit_width is not None and type_info.bit_width < 1:
                    compiler.error(
                        f'El ancho de {type_info.name} debe ser mayor que cero: {name}'
                    )
            compiler.storage.define_function(FunctionSymbol(name, signature))


def validate(compiler: Compiler, node: gast.ASTRef):
    compiler.debug(f'Validando funcion Bagron: {node}')
    return node

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.frontend.objects import Variable

if TYPE_CHECKING:
    from core.compiler import Compiler
from gram import ast as gast


def _declarator_info(node: gast.ASTRef):
    is_const = False
    name = ''
    pointer_level = 0

    for child in node.nodes:
        if isinstance(child, gast.ASTKeyword):
            is_const = child.token.value == 'const'
        elif isinstance(child, gast.ASTRef) and child.name == 'POINTER':
            pointer_level = len(child.nodes)
        else:
            token = getattr(child, 'token', None)
            if token is not None:
                name = str(token.value)

    return name, pointer_level, is_const


def _type_is_const(node: object) -> bool:
    if isinstance(node, list):
        return any(_type_is_const(item) for item in node)

    if isinstance(node, gast.ASTRef):
        return _type_is_const(node.nodes)

    token = getattr(node, 'token', None)
    return token is not None and token.value == 'const'

def _type_name(node: object) -> str:
    if isinstance(node, list):
        return ''.join(_type_name(item) for item in node)

    if isinstance(node, gast.ASTRef):
        return _type_name(node.nodes)

    token = getattr(node, 'token', None)
    if token is not None:
        return '' if token.value == 'const' else str(token.value)

    return str(getattr(node, 'value', ''))


def _bitint_info(type_name: str) -> tuple[int, bool] | None:
    match = re.fullmatch(r'(u?Bint)<(\d+)>(?:\[\])*', type_name)
    if match is None:
        return None
    return int(match.group(2)), match.group(1) == 'Bint'


def _bare_identifier(node: object) -> str | None:
    if isinstance(node, gast.ASTRef):
        if node.name == 'VALUE' and len(node.nodes) == 1:
            return _bare_identifier(node.nodes[0])
        if node.name == 'POSTFIX_EXPR' and len(node.nodes) == 1:
            return _bare_identifier(node.nodes[0])
        if node.name == 'PRIMARY' and len(node.nodes) == 1:
            return _bare_identifier(node.nodes[0])
        return None

    token = getattr(node, 'token', None)
    token_kind = getattr(getattr(token, 'token', None), 'name', None)
    if token_kind == 'IDENT':
        return str(getattr(token, 'value', ''))

    return None

def validate(compiler: Compiler, node: gast.ASTRef):
    nodes: list[gast.ASTRef | gast.ASTKeyword] = node.nodes # type: ignore
    privacy: str = compiler.storage.privacy
    
    # Si nodes es una lista de dos elementos, el primero siempre será el KEYWORD de privacidad.
    if len(nodes) == 2:
        privacy = str(nodes[0].token.value) # type: ignore
        node = nodes[1] # type: ignore
    else: # de lo contrario, será una lista con un solo elemento.
        node = nodes[0] # type: ignore
    
    nodes: list[gast.ASTRef | gast.ASTKeyword] = node.nodes # type: ignore
    declarator = nodes[0]
    name, pointer_level, pointer_is_const = _declarator_info(declarator)
    type_node = nodes[2]
    type_ = _type_name(type_node)
    value_is_const = _type_is_const(type_node)

    if node.name == 'VAR_DECLARATION': # contiene ASSIGN y VALUE
        value = nodes[4]

        
    else: # VAR_INITIALIZATION no contine ASSIGN ni VALUE.
        value = None
        
    var = Variable(name, type_, pointer_level, value)
    var.is_const = value_is_const
    var.value_is_const = value_is_const
    var.pointer_is_const = pointer_is_const

    bitint = _bitint_info(type_)
    if bitint is not None:
        var.bit_width, var.signed = bitint
        if var.bit_width < 1:
            compiler.error(f'El ancho de {type_} debe ser mayor que cero: {name}')

    if type_ == 'callptr':
        var.pointer_size = compiler.storage.pointer_size
        if pointer_level == 0:
            compiler.error(f'El tipo callptr requiere al menos un nivel de puntero: {name}')
        elif value is not None:
            target_name = _bare_identifier(value)
            function = compiler.storage.functions.get(target_name) if target_name else None
            source = compiler.storage.namespace.get(target_name) if target_name else None

            if function is not None:
                var.call_signature = function.signature
            elif source is not None and getattr(source, 'call_signature', None) is not None:
                var.call_signature = source.call_signature
            else:
                compiler.error(
                    f'El inicializador de {name} debe ser una función o un callptr compatible'
                )
    
    # procesar tipos y otras cosas.
    
    # .
    
    return name, var        

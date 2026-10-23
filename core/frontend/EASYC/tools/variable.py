from __future__ import annotations

from typing import TYPE_CHECKING

from core.frontend.EASYC.objects import Variable

if TYPE_CHECKING:
    from core.compiler import Compiler
from gram import ast as gast


def _handle_const(nodes: list[gast.ASTRef | gast.ASTKeyword]):
    node = nodes[0]
    if isinstance(node, gast.ASTKeyword):  # noqa: SIM102
        if node.token.value == 'const':
            return True, nodes[1:]
    return False, nodes

def _handle_pointer(nodes: list[gast.ASTRef | gast.ASTKeyword]):
    node = nodes[0]
    if isinstance(node, gast.ASTRef):  # noqa: SIM102
        if node.name == 'POINTER':
            return len(node.nodes), nodes[1:]
        
    return 0, nodes

def validate(compiler: Compiler, node: gast.ASTRef):
    nodes: list[gast.ASTRef | gast.ASTKeyword] = node.nodes # type: ignore
    is_const: bool = False
    privacy: str = compiler.storage.privacy
    pointer_level: int = 0
    
    # Si nodes es una lista de dos elementos, el primero siempre será el KEYWORD de privacidad.
    if len(nodes) == 2:
        privacy = str(nodes[0].token.value) # type: ignore
        node = nodes[1] # type: ignore
    else: # de lo contrario, será una lista con un solo elemento.
        node = nodes[0] # type: ignore
    
    nodes: list[gast.ASTRef | gast.ASTKeyword] = node.nodes # type: ignore
    is_const, nodes = _handle_const(nodes) # el primer valor siempre será const si se define const

    # al reducir const, el valor siguiente será el nombre (IDENT)
    name = str(nodes[0].token.value) # type: ignore 
    # por supuesto, después del IDENT viene una bolsa de STAR opcional (Puntero)
    pointer_level, nodes = _handle_pointer(nodes[1:])
    
    # Valores actuales deben ser COLON, KEYWORD, [ ASSIGN, VALUE ] ASSIGN y VALUE pueden no estar. Depende del tipo de ASTRef.
    type_ = nodes[1].token.value # type: ignore

    if node.name == 'VAR_DECLARATION': # contiene ASSIGN y VALUE
        value = nodes[3]

        
    else: # VAR_INITIALIZATION no contine ASSIGN ni VALUE.
        value = None
        
    var = Variable(name, type_, pointer_level, value)
    var.is_const = name.isupper()
    var.pointer_is_const = is_const
    
    # procesar tipos y otras cosas.
    
    # .
    
    return name, var        

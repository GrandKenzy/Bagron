from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.compiler import Compiler
from gram import ast as gast

def _handle_const(nodes: list[gast.ASTRef | gast.ASTKeyword]):
    node = nodes[0]
    if isinstance(node, gast.ASTKeyword):
        if node.token.value == 'const':
            return True, nodes[1:]
    return False, nodes

def _handle_pointer(nodes: list[gast.ASTRef | gast.ASTKeyword]):
    node = nodes[0]
    if isinstance(node, gast.ASTRef):
        if node.name == 'POINTER':
            return len(node.nodes), nodes[1:]
        
    return 0, nodes

def validate(compiler: Compiler, node: gast.ASTRef):
    nodes: list[gast.ASTRef | gast.ASTKeyword] = node.nodes
    is_const: bool = False
    privacy: bool = False
    pointer_level: int = 0
    
    if len(nodes) == 2:
        privacy = nodes[0].token.value
        node = nodes[1] # type: ignore
    else:
        node = nodes[0] # type: ignore
    
    nodes: list[gast.ASTRef | gast.ASTKeyword] = node.nodes # type: ignore
    is_const, nodes = _handle_const(nodes)

    name: gast.ASTTokenNode = nodes[0] # type: ignore
    pointer_level, nodes = _handle_pointer(nodes[1:])
    
    

    if node.name == 'VAR_DECLARATION':
        pass
        
    else:
        pass
        

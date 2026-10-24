from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.compiler import Compiler
from gram import ast as gast


def _handle_pointer(nodes: list[gast.ASTRef | gast.ASTKeyword]):
    if not nodes:
        return 0, nodes
    node = nodes[0]
    if isinstance(node, gast.ASTRef) and node.name == 'POINTER':
        return len(node.nodes), nodes[1:]
    return 0, nodes


def validate(compiler: Compiler, node: gast.ASTRef):
    """Valida y extrae informacion semantica de una variable (tipo, puntero, nombre, init)."""
    compiler.debug(f'validando variable e n C: {node}')
    inner = node.nodes[0] if node.nodes else node
    compiler.debug(f'definicion de la variable extraida: {inner.name}')
    return inner

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.compiler import Compiler
from gram import ast as gast


def validate(compiler: Compiler, node: gast.ASTRef):
    """validar y extraer el prototyp o definicion de funcion"""
    compiler.debug(f'Validando función C: {node}')
    return node

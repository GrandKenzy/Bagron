from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.compiler import Compiler
from gram import ast as gast


def validate(compiler: Compiler, node: gast.ASTRef):
    # punto de ejecucion
    compiler.debug(f'Validando funcion EC: {node}')
    return node

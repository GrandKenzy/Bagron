from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.compiler import Compiler
from gram import ast as gast


def validate(compiler: Compiler, node: gast.ASTRef):
    # ciclo de vida encapsulado
    compiler.debug(f'Validando clase EC: {node}')
    return node

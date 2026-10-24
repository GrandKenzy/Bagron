from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.compiler import Compiler
from gram import ast as gast


def validate(compiler: Compiler, node: gast.ASTRef):
    """Valida typedef en C."""
    compiler.debug(f'Validando typedef C: {node}')
    return node

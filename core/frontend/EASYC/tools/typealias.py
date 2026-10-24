from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.compiler import Compiler
from gram import ast as gast


def validate(compiler: Compiler, node: gast.ASTRef):
    # sustitucion de tipo
    compiler.debug(f'Validando typealias EC: {node}')
    return node

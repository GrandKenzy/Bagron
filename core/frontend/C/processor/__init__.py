from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.compiler import Compiler
from gram import ast as gast

from core.frontend.C import tools


def process(compiler: Compiler, nodes: list[gast.ASTRef]):
    compiler.debug('Se recibii la ruta de procesamiento. Procesando AST para C fram.')

    for node in nodes:
        name: str = node.name
        if name == 'VAR':
            tools.variable.validate(compiler, node)
        elif name == 'FUNCTION':
            tools.function.validate(compiler, node)
        elif name == 'INCLUDE':
            tools.includes.validate(compiler, node)
        elif name in ('STRUCT', 'UNION'):
            tools.structure.validate(compiler, node)
        elif name == 'ENUM':
            tools.enumeration.validate(compiler, node)
        elif name == 'TYPEDEF':
            tools.typedef.validate(compiler, node)
        elif name in ('IF', 'WHILE', 'DO_WHILE', 'FOR', 'CALL_STMT', 'PRAGMA'):
            compiler.debug(f'Sentencia C procesada: {name}')
        else:
            compiler.error(f'Falta por resolver {node}')
            compiler.exit()

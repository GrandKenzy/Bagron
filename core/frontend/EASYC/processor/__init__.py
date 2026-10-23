from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.compiler import Compiler
from gram import ast as gast

from core.frontend.EASYC import tools


def process(compiler: Compiler, nodes: list[gast.ASTRef]):
    compiler.debug('Se recibió la ruta de procesamiento. Procesando AST para EC.')
    
    for node in nodes:
        name: str = node.name
        if name == 'CLAUSE':
            compiler.storage.define_clause(*tools.clauses.validate(node))
            
        elif name == 'VAR':
            tools.variable.validate(compiler, node)         
        
    
        else:
            compiler.error(f'Falta por resolver {node}')
            compiler.exit()
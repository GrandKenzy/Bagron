from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.compiler import Compiler
from gram import ast as gast

from core.frontend import tools


def process(compiler: Compiler, nodes: list[gast.ASTRef]):
    compiler.debug('Se recibió la ruta de procesamiento. Procesando AST para Bagron.')

    # Las clausulas deben resolverse antes de variables para fijar target,
    # visibilidad y demas opciones independientemente del orden del archivo.
    for node in nodes:
        if node.name == 'CLAUSE':
            try:
                compiler.storage.define_clause(*tools.clauses.validate(node))
            except ValueError as error:
                compiler.error(str(error))

    tools.structure.collect(compiler, nodes)
    tools.enumeration.collect(compiler, nodes)
    tools.function.collect(compiler, nodes)

    for node in nodes:
        name: str = node.name
        if name == 'CLAUSE':
            continue
        elif name == 'VAR':
            tools.variable.collect_global(compiler, node)

        elif name == 'FUNCTION':
            tools.function.process(compiler, node)

        elif name == 'CLASS':
            tools.classes.validate(compiler, node)

        elif name in ('STRUCT', 'MOLD', 'FLAGS'):
            tools.structure.validate(compiler, node)

        elif name == 'ENUM':
            tools.enumeration.validate(compiler, node)

        elif name == 'TYPEALIAS':
            tools.typealias.validate(compiler, node)

        elif name == 'IMPORT':
            tools.imports.validate(compiler, node)

        elif name in ('IF', 'WHILE', 'FOR', 'CALL', 'VAR_ASSIGNATION'):
            # flujo secuencial
            compiler.debug(f'Sentencia Bagron procesada: {name}')

        else:
            compiler.error(f'Falta por resolver {node}')
            compiler.exit()

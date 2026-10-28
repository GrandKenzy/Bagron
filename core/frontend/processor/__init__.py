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
        if node.name == 'EXTERN':
            tools.externs.collect(compiler, node)

    # Complete nominal aggregate/enum definitions before validating global
    # initializers.  A global such as ``ptr *: int = $point.x`` needs the
    # struct field table during semantic inference, even when the declaration
    # appears before the type's source body is visited in the normal pass.
    for node in nodes:
        if node.name in ('STRUCT', 'MOLD', 'FLAGS'):
            tools.structure.validate(compiler, node)
        elif node.name == 'ENUM':
            tools.enumeration.validate(compiler, node)

    global_nodes = [node for node in nodes if node.name == 'VAR']
    for node in global_nodes:
        # Register every global first so address initializers can refer to a
        # declaration that appears later in the file.
        tools.variable.collect_global(compiler, node, validate=False)

    for node in global_nodes:
        handle = tools.variable.handle_variable(node)
        if handle is None:
            continue
        symbol = compiler.storage.namespace.get(handle.name)
        if symbol is not None:
            tools.variable.validate_initializer(
                compiler,
                compiler.storage,
                handle,
                symbol,
            )

    tools.imports.bind_aliases(compiler)

    for node in nodes:
        name: str = node.name
        if name == 'CLAUSE':
            continue
        elif name == 'VAR':
            continue

        elif name == 'FUNCTION':
            tools.function.process(compiler, node)

        elif name == 'CLASS':
            tools.classes.validate(compiler, node)

        elif name in ('STRUCT', 'MOLD', 'FLAGS', 'ENUM'):
            # Definitions were validated before globals so postfix/member
            # initializers can resolve their fields.
            continue

        elif name == 'TYPEALIAS':
            tools.typealias.validate(compiler, node)

        elif name == 'IMPORT':
            tools.imports.validate(compiler, node)

        elif name == 'INCLUDE':
            tools.includes.validate(compiler, node)

        elif name == 'EXTERN':
            continue

        elif name in ('IF', 'WHILE', 'FOR', 'CALL', 'VAR_ASSIGNATION'):
            # flujo secuencial
            compiler.debug(f'Sentencia Bagron procesada: {name}')

        else:
            compiler.error(f'Falta por resolver {node}')
            compiler.exit()

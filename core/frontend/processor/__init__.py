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
        compiler.activate_module(compiler.module_for_node(node))
        if node.name == 'CLAUSE':
            try:
                clause_name, clause_value = tools.clauses.validate(node)
                module_path = compiler.module_for_node(node)
                if (
                    clause_name in ('System', 'Arch', 'Boot')
                    and module_path != compiler.main_module_path
                ):
                    # Imported modules are checked against the entry-module
                    # target before this pass.  Their target clauses must not
                    # overwrite the single backend target selected by main.
                    continue
                compiler.storage.define_clause(clause_name, clause_value)
            except ValueError as error:
                compiler.error(str(error))

    tools.structure.collect(compiler, nodes)
    tools.enumeration.collect(compiler, nodes)
    tools.function.collect(compiler, nodes)
    for node in nodes:
        compiler.activate_module(compiler.module_for_node(node))
        if node.name == 'EXTERN':
            tools.externs.collect(compiler, node)

    # Complete nominal aggregate/enum definitions before validating global
    # initializers.  A global such as ``ptr *: int = $point.x`` needs the
    # struct field table during semantic inference, even when the declaration
    # appears before the type's source body is visited in the normal pass.
    for node in nodes:
        compiler.activate_module(compiler.module_for_node(node))
        if node.name == 'CLASS':
            tools.classes.validate(compiler, node)
        elif node.name in ('STRUCT', 'MOLD', 'FLAGS'):
            tools.structure.validate(compiler, node)
        elif node.name == 'ENUM':
            tools.enumeration.validate(compiler, node)

    tools.classes.validate_inheritance(compiler, nodes)

    # Class fields are needed before method scopes can expose them.  Register
    # every method before processing any function body so calls can be resolved
    # regardless of source order.
    tools.classes.collect_methods(compiler, nodes)

    tools.structure.validate_value_cycles(compiler)

    global_nodes = [node for node in nodes if node.name == 'VAR']
    for node in global_nodes:
        compiler.activate_module(compiler.module_for_node(node))
        # Register every global first so address initializers can refer to a
        # declaration that appears later in the file.
        tools.variable.collect_global(compiler, node, validate=False)

    for node in global_nodes:
        compiler.activate_module(compiler.module_for_node(node))
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
        compiler.activate_module(compiler.module_for_node(node))
        name: str = node.name
        if name == 'CLAUSE':
            continue
        elif name == 'VAR':
            continue

        elif name == 'FUNCTION':
            tools.function.process(compiler, node)

        elif name == 'CLASS':
            # Classes were lowered to their struct representation before
            # global initializers are checked.  Methods remain deferred.
            continue

        elif name in ('STRUCT', 'MOLD', 'FLAGS', 'ENUM'):
            # Definitions were validated before globals so postfix/member
            # initializers can resolve their fields.
            continue

        elif name == 'IMPORT':
            tools.imports.validate(compiler, node)

        elif name == 'EXTERN':
            continue

        elif name in ('IF', 'WHILE', 'FOR', 'CALL', 'VAR_ASSIGNATION'):
            # flujo secuencial
            compiler.debug(f'Sentencia Bagron procesada: {name}')

        else:
            compiler.error(f'Falta por resolver {node}')
            compiler.exit()

    # Methods live inside CLASS nodes rather than in the top-level function
    # list, but use the same body validator and local-variable collector.
    tools.classes.process_methods(compiler, nodes)
    compiler.activate_module(None)

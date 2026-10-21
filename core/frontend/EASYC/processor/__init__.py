from gram import ast

from core.processor import magic_methods, visitors
from core.processor.storage import Storage


def process(storage: Storage, nodes: list[ast.ASTRef]):
    for node in nodes:
        
        # extensiones
        # @ Stable
        if node.name == 'CLAUSE':
            visitors.visit_clause(storage, node)


        # unestable
        elif node.name == 'IMPORT':
            visitors.visit_import(storage, node)

        elif node.name == 'INCLUDE':
            visitors.visit_include(storage, node)

        # declaradores
        elif node.name == 'VAR_DECL':
            visitors.visit_var(storage, node)

        # asignaciones
        elif node.name == 'VAR_ASSIGNATION':
            assign_obj = visitors.visit_assign(storage, node)
            storage.statements.append(assign_obj)

        # enums
        elif node.name == 'ENUM':
            visitors.visit_enum(storage, node)

        # structs, molds, flags
        elif node.name in ('STRUCT', 'FLAGS', 'MOLD'):
            visitors.visit_struct(storage, node)

        # clases
        elif node.name == 'CLASS':
            visitors.visit_class(storage, node)

        # alias de tipo
        elif node.name in ('TYPEALIAS', 'TYPE'):
            visitors.visit_typealias(storage, node)

        # funciones
        elif node.name in ('FUNCTION', 'DECORATED_FUNCTION'):
            visitors.visit_func(storage, node)

        # bucles
        elif node.name == 'WHILE':
            visitors.visit_while(storage, node)

        elif node.name == 'FOR':
            visitors.visit_for(storage, node)

        # condicionales
        elif node.name == 'IF':
            visitors.visit_if(storage, node)

        # llamadas y miembros
        elif node.name == 'CALL':
            call_obj = visitors.visit_call(storage, node)
            storage.statements.append(call_obj)

        elif node.name == 'MEMBER_CHAIN':
            chain_obj = visitors.visit_member_chain(storage, node)
            storage.statements.append(chain_obj)

        elif node.name == 'INDEX_ACCESS':
            idx_obj = visitors.visit_index_access(storage, node)
            storage.statements.append(idx_obj)


__all__ = [
    'magic_methods',
    'process',
]
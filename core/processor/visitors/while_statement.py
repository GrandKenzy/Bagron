from typing import Any
from gram import ast
from core.processor.objects.function import LocalStorage
from core.processor.objects.while_statement import WhileStatement
from core.processor.storage import Storage
from core.processor.visitors.var_decl import infer_value_type


def visit_while(storage: Any, node: ast.ASTRef, in_loop: bool = True, is_nested: bool = False) -> WhileStatement:
    # 1. Extraer condición y cuerpo

    # node.nodes: [KEYWORD('while'), WHILE_CONDITION, COLON, WHILE_BODY]
    condition_node: ast.ASTRef = node.nodes[1]  # type: ignore
    body_node: ast.ASTRef = node.nodes[3]  # type: ignore

    # Condición
    condition_value = condition_node.nodes[0] if condition_node.nodes else None

    # Inferencia de la condición
    if condition_value is not None:
        _ = infer_value_type(storage, condition_value)  # type: ignore

    # 2. Extraer sentencias del cuerpo
    statements = body_node.nodes[1] if len(body_node.nodes) > 1 and isinstance(body_node.nodes[1], list) else []

    processed_body: list[Any] = []

    from core.processor.visitors.assign import visit_assign
    from core.processor.visitors.var_decl import visit_var

    for child in statements:
        if isinstance(child, ast.ASTKeyword):
            if child.token.value == 'pass':
                processed_body.append(child)
                continue

        if isinstance(child, ast.ASTRef):
            if child.name == 'SKIPER':
                # break / continue dentro del bucle
                processed_body.append(child)

            elif child.name == 'VAR_DECL':
                var_obj = visit_var(storage, child)
                if isinstance(var_obj, list):
                    processed_body.extend(var_obj)
                else:
                    processed_body.append(var_obj)

            elif child.name == 'VAR_ASSIGNATION':
                visit_assign(storage, child)
                processed_body.append(child)

            elif child.name == 'WHILE':
                # Recursión limpia para bucles while anidados
                nested_while = visit_while(storage, child, in_loop=True, is_nested=True)
                processed_body.append(nested_while)

            elif child.name == 'FOR':
                from core.processor.visitors.for_statement import visit_for
                nested_for = visit_for(storage, child, is_nested=True)
                processed_body.append(nested_for)

            elif child.name == 'IF':
                from core.processor.visitors.if_statement import visit_if
                nested_if = visit_if(storage, child, in_loop=True, is_nested=True)
                processed_body.append(nested_if)

            elif child.name == 'RETURN':
                # Si estamos dentro de una función, validamos reglas de return
                func = storage.function if isinstance(storage, LocalStorage) else None
                has_value = len(child.nodes) > 1 and child.nodes[1] is not None
                if func is not None:
                    if func.return_type == 'void' and has_value:
                        raise RuntimeError(f"La función '{func.name}' de tipo 'void' no puede retornar un valor.")
                    if func.return_type != 'void' and not has_value:
                        raise RuntimeError(f"La función '{func.name}' de tipo '{func.return_type}' debe retornar un valor, no void.")
                processed_body.append(child)

            elif child.name == 'CALL':
                from core.processor.visitors.call import visit_call
                call_obj = visit_call(storage, child)
                processed_body.append(call_obj)

            elif child.name == 'MEMBER_CHAIN':
                from core.processor.visitors.call import visit_member_chain
                chain_obj = visit_member_chain(storage, child)
                processed_body.append(chain_obj)

            elif child.name == 'INDEX_ACCESS':
                from core.processor.visitors.call import visit_index_access
                idx_obj = visit_index_access(storage, child)
                processed_body.append(idx_obj)

            else:
                processed_body.append(child)

    while_obj = WhileStatement(condition=condition_value, body=processed_body, in_scope=storage)

    # Si estamos en Storage global (top level), registrar en storage.statements
    if not is_nested and isinstance(storage, Storage):
        storage.statements.append(while_obj)

    return while_obj


__all__ = [
    'visit_while',
]

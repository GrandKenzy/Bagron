from typing import Any

from gram import ast

from core.processor.objects.function import LocalStorage
from core.processor.objects.if_statement import ElifClause, IfStatement
from core.processor.storage import Storage
from core.processor.visitors.var_decl import infer_value_type, validate_type


def _process_if_body(storage: Any, statements: list[Any], in_loop: bool) -> list[Any]:
    """Procesa una lista de sentencias dentro del cuerpo de un bloque if/elif/else."""
    processed: list[Any] = []

    from core.processor.visitors.assign import visit_assign
    from core.processor.visitors.var_decl import visit_var

    for child in statements:
        if isinstance(child, ast.ASTKeyword):
            if child.token.value == 'pass':
                processed.append(child)
                continue

        if isinstance(child, ast.ASTRef):
            if child.name == 'SKIPER':
                if not in_loop:
                    token_val = child.nodes[0].token.value if child.nodes and isinstance(child.nodes[0], ast.ASTTokenNode) else 'skiper'
                    raise RuntimeError(f"'{token_val}' no se puede utilizar fuera de un bucle.")
                processed.append(child)

            elif child.name == 'VAR_DECL':
                var_obj = visit_var(storage, child)
                if isinstance(var_obj, list):
                    processed.extend(var_obj)
                else:
                    processed.append(var_obj)

            elif child.name == 'VAR_ASSIGNATION':
                visit_assign(storage, child)
                processed.append(child)

            elif child.name == 'WHILE':
                from core.processor.visitors.while_statement import visit_while
                nested_while = visit_while(storage, child, in_loop=True, is_nested=True)
                processed.append(nested_while)

            elif child.name == 'FOR':
                from core.processor.visitors.for_statement import visit_for
                nested_for = visit_for(storage, child, is_nested=True)
                processed.append(nested_for)

            elif child.name == 'IF':
                nested_if = visit_if(storage, child, in_loop=in_loop, is_nested=True)
                processed.append(nested_if)

            elif child.name == 'RETURN':
                func = storage.function if isinstance(storage, LocalStorage) else None
                has_value = len(child.nodes) > 1 and child.nodes[1] is not None
                if func is not None:
                    if func.return_type == 'void' and has_value:
                        raise RuntimeError(f"La función '{func.name}' de tipo 'void' no puede retornar un valor.")
                    if func.return_type != 'void' and not has_value:
                        raise RuntimeError(f"La función '{func.name}' de tipo '{func.return_type}' debe retornar un valor, no void.")
                    if has_value:
                        inferred = infer_value_type(storage, child.nodes[1])  # type: ignore
                        if inferred is not None:
                            validate_type(func.name, func.return_type, inferred, storage=storage)
                processed.append(child)

            elif child.name == 'CALL':
                from core.processor.visitors.call import visit_call
                call_obj = visit_call(storage, child)
                processed.append(call_obj)

            elif child.name == 'MEMBER_CHAIN':
                from core.processor.visitors.call import visit_member_chain
                chain_obj = visit_member_chain(storage, child)
                processed.append(chain_obj)

            elif child.name == 'INDEX_ACCESS':
                from core.processor.visitors.call import visit_index_access
                idx_obj = visit_index_access(storage, child)
                processed.append(idx_obj)

            else:
                processed.append(child)

    return processed


def visit_if(storage: Any, node: ast.ASTRef, in_loop: bool = False, is_nested: bool = False) -> IfStatement:
    # 1. Extraer condición y cuerpo de if

    # node.nodes: [KEYWORD('if'), CONDITION, COLON, IF_BODY, (Many(ELIF)), (Opt(ELSE))]
    condition_node: ast.ASTRef = node.nodes[1]  # type: ignore
    body_node: ast.ASTRef = node.nodes[3]  # type: ignore

    condition_value = condition_node.nodes[0] if condition_node.nodes else None
    if condition_value is not None:
        _ = infer_value_type(storage, condition_value)  # type: ignore

    statements = body_node.nodes[1] if len(body_node.nodes) > 1 and isinstance(body_node.nodes[1], list) else []
    processed_body = _process_if_body(storage, statements, in_loop)

    # 2. Extraer ramas ELIF y ELSE
    elif_nodes: list[ast.ASTRef] = []
    else_node: ast.ASTRef | None = None

    for extra in node.nodes[4:]:
        if isinstance(extra, list):
            for item in extra:
                if isinstance(item, ast.ASTRef) and item.name == 'ELIF':
                    elif_nodes.append(item)
        elif isinstance(extra, ast.ASTRef):
            if extra.name == 'ELIF':
                elif_nodes.append(extra)
            elif extra.name == 'ELSE':
                else_node = extra

    # 3. Procesar ELIFs
    processed_elifs: list[ElifClause] = []
    for elif_ast in elif_nodes:
        # elif_ast.nodes: [KEYWORD('elif'), CONDITION, COLON, IF_BODY]
        e_cond_node = elif_ast.nodes[1]
        e_cond_val = e_cond_node.nodes[0] if e_cond_node.nodes else None
        if e_cond_val is not None:
            _ = infer_value_type(storage, e_cond_val)  # type: ignore

        e_body_node = elif_ast.nodes[3]
        e_stmts = e_body_node.nodes[1] if len(e_body_node.nodes) > 1 and isinstance(e_body_node.nodes[1], list) else []
        e_proc_body = _process_if_body(storage, e_stmts, in_loop)
        processed_elifs.append(ElifClause(condition=e_cond_val, body=e_proc_body))

    # 4. Procesar ELSE
    processed_else: list[Any] = []
    if else_node is not None:
        # else_node.nodes: [KEYWORD('else'), COLON, IF_BODY]
        else_body_node = else_node.nodes[2]
        else_stmts = else_body_node.nodes[1] if len(else_body_node.nodes) > 1 and isinstance(else_body_node.nodes[1], list) else []
        processed_else = _process_if_body(storage, else_stmts, in_loop)

    # 5. Crear IfStatement
    if_obj = IfStatement(
        condition=condition_value,
        body=processed_body,
        elifs=processed_elifs,
        else_body=processed_else,
        in_scope=storage,
    )

    # Si estamos en Storage global (top level), registrar en storage.statements
    if not is_nested and isinstance(storage, Storage):
        storage.statements.append(if_obj)

    return if_obj


__all__ = [
    'visit_if',
]
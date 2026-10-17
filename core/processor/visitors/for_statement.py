from typing import Any
from gram import ast
from core.processor.objects.for_statement import ForStatement
from core.processor.objects.function import FunctionParam, LocalStorage
from core.processor.objects.variable import Variable
from core.processor.storage import Storage


def _extract_target_names(targets_node: ast.ASTRef) -> list[str]:
    """Extrae los nombres de variables objetivo de FOR_TARGETS."""
    raw_targets = targets_node.nodes
    if len(raw_targets) > 0 and isinstance(raw_targets[0], ast.ArrayNode):
        raw_targets = raw_targets[0].items

    targets: list[str] = []
    for t in raw_targets:
        if isinstance(t, ast.ASTTokenNode):
            targets.append(t.token.value)
        elif isinstance(t, str):
            targets.append(t)
    return targets


def _infer_loop_var_type(storage: Any, mode: str, iterable_node: ast.ASTRef) -> str:
    """Infiere el tipo de la variable del bucle según el modo de iteración."""
    if mode in ('ran', 'index'):
        return 'int'

    # Para 'in' o 'iter', intentamos deducir de la colección
    target_node = iterable_node
    if target_node.name == 'ITERABLE' and len(target_node.nodes) > 0:
        target_node = target_node.nodes[0]

    if target_node.name == 'VALUE' and len(target_node.nodes) > 0:
        target = target_node.nodes[0]
        if isinstance(target, ast.ASTRef) and target.name == 'DUALEXPR' and len(target.nodes) == 1:
            target = target.nodes[0]

        if isinstance(target, ast.ASTTokenNode) and 'IDENT' in str(target.token.token):
            ref = storage.resolve(target.token.value)
            if isinstance(ref, (Variable, FunctionParam)):
                col_type = ref.type
                if col_type.startswith('array[') and ',' in col_type:
                    inner = col_type[len('array['):col_type.find(',')].strip()
                    return inner
                if col_type == 'chain':
                    return 'char'


    return 'int'


def visit_for(storage: Any, node: ast.ASTRef, is_nested: bool = False) -> ForStatement:
    # 1. Extraer componentes sintácticos

    # node.nodes: [KEYWORD('for'), FOR_TARGETS, ITERS, ITERABLE, COLON, FOR_BODY]
    targets_node: ast.ASTRef = node.nodes[1]  # type: ignore
    iter_token = node.nodes[2]
    mode: str = iter_token.token.value if isinstance(iter_token, ast.ASTTokenNode) else str(iter_token)  # type: ignore
    iterable_node: ast.ASTRef = node.nodes[3]  # type: ignore
    body_node: ast.ASTRef = node.nodes[5]  # type: ignore

    # Variables objetivo
    targets = _extract_target_names(targets_node)

    # Inferencia del tipo de la variable de bucle
    loop_var_type = _infer_loop_var_type(storage, mode, iterable_node)

    # Registrar variables de bucle en el ámbito si no existen
    for target_name in targets:
        existing = storage.resolve(target_name)
        if existing is None:
            storage.add_variable(name=target_name, var_type=loop_var_type, privacy='public')

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
                from core.processor.visitors.while_statement import visit_while
                nested_while = visit_while(storage, child, in_loop=True, is_nested=True)
                processed_body.append(nested_while)

            elif child.name == 'FOR':
                nested_for = visit_for(storage, child, is_nested=True)
                processed_body.append(nested_for)

            elif child.name == 'IF':
                from core.processor.visitors.if_statement import visit_if
                nested_if = visit_if(storage, child, in_loop=True, is_nested=True)
                processed_body.append(nested_if)

            elif child.name == 'RETURN':
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

    for_obj = ForStatement(targets=targets, mode=mode, iterable=iterable_node, body=processed_body, in_scope=storage)

    # Si estamos en Storage global (top level), registrar en storage.statements
    if not is_nested and isinstance(storage, Storage):
        storage.statements.append(for_obj)

    return for_obj


__all__ = [
    'visit_for',
]

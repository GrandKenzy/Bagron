from typing import Any

from gram import ast

from core.processor.objects.function import Function, FunctionParam, LocalStorage
from core.processor.storage import Storage
from core.processor.visitors.var_decl import (
    extract_type,
    infer_value_type,
    validate_type,
)


def process_decorators(storage: Storage, func: Function, node: ast.ASTRef | None) -> list[str]:
    """Procesa los decoradores de la función y los asigna a func.decorators."""
    if not node or not node.nodes:
        func.decorators = []
        return []

    raw_list = node.nodes[0] if len(node.nodes) > 0 and isinstance(node.nodes[0], list) else node.nodes
    decorators: list[str] = []

    for item in raw_list:
        if isinstance(item, ast.ASTRef) and item.name == 'DECORATOR':
            dec_name = item.nodes[1].token.value
            decorators.append(dec_name)

    func.decorators = decorators
    return decorators


def process_parameters(local_storage: LocalStorage, func: Function, params_node: ast.ASTRef) -> list[FunctionParam]:
    """Extrae y valida los parámetros de la función dentro de su LocalStorage."""
    raw_params = []
    if len(params_node.nodes) > 0:
        first = params_node.nodes[0]
        if isinstance(first, ast.ArrayNode):
            raw_params = first.items
        elif isinstance(first, list):
            raw_params = first

    params: list[FunctionParam] = []
    seen_variadic = False
    seen_default = False

    for p in raw_params:
        if not isinstance(p, ast.ASTRef):
            continue

        if p.name == 'PAIR_PARAM':
            if seen_variadic:
                raise SyntaxError(
                    f"En '{func.name}': los parámetros posicionales no pueden ir después de '*args'."
                )
            if seen_default:
                raise SyntaxError(
                    f"En '{func.name}': los parámetros posicionales no pueden ir después de un parámetro con valor por defecto."
                )
            p_name: str = p.nodes[0].token.value  # type: ignore
            p_type: str = extract_type(p.nodes[2])  # type: ignore
            if p_name in ('self', 'cls'):
                raise RuntimeError(f"No se puede usar el identificador reservado '{p_name}' como nombre de parámetro.")
            local_storage.collition_name(p_name)
            param_obj = FunctionParam(name=p_name, param_type=p_type)
            params.append(param_obj)
            local_storage.parameters[p_name] = param_obj

        elif p.name == 'VARIADIC_PARAM':
            if seen_variadic:
                raise SyntaxError(
                    f"En '{func.name}': solo se permite un parámetro variádico '*args'."
                )
            if seen_default:
                raise SyntaxError(
                    f"En '{func.name}': el parámetro variádico '*args' no puede ir después de parámetros con valor por defecto."
                )
            seen_variadic = True
            p_name = p.nodes[1].token.value
            p_type = extract_type(p.nodes[3])
            if p_name in ('self', 'cls'):
                raise RuntimeError(f"No se puede usar el identificador reservado '{p_name}' como nombre de parámetro.")
            local_storage.collition_name(p_name)
            param_obj = FunctionParam(name=p_name, param_type=p_type, is_variadic=True)
            params.append(param_obj)
            local_storage.parameters[p_name] = param_obj

        elif p.name == 'PAIR_DECLARE_PARAM':
            seen_default = True
            pair: ast.ASTRef = p.nodes[0]  # type: ignore
            p_name = pair.nodes[0].token.value  # type: ignore
            p_type = extract_type(pair.nodes[2])  # type: ignore
            default_val = p.nodes[2]
            if p_name in ('self', 'cls'):
                raise RuntimeError(f"No se puede usar el identificador reservado '{p_name}' como nombre de parámetro.")
            local_storage.collition_name(p_name)

            # Validar que el valor por defecto coincida con el tipo declarado (FNC-03 / CAL-01)
            if default_val is not None:
                inferred_def = infer_value_type(local_storage, default_val)
                if inferred_def is not None and p_type not in ('any', 'ptr'):
                    validate_type(p_name, p_type, inferred_def, storage=local_storage)


            param_obj = FunctionParam(name=p_name, param_type=p_type, default=default_val, has_default=True)
            params.append(param_obj)
            local_storage.parameters[p_name] = param_obj

    func.parameters = params
    return params


def process_body(local_storage: LocalStorage, func: Function, body_node: ast.ASTRef) -> list[Any]:
    """Procesa las sentencias del cuerpo de la función dentro del ámbito local."""
    statements = body_node.nodes[1] if len(body_node.nodes) > 1 and isinstance(body_node.nodes[1], list) else []
    body_items: list[Any] = []

    from core.processor.visitors.assign import visit_assign
    from core.processor.visitors.var_decl import visit_var

    for child in statements:
        if isinstance(child, ast.ASTKeyword):  # noqa: SIM102
            if child.token.value == 'pass':
                body_items.append(child)
                continue

        if isinstance(child, ast.ASTRef):
            if child.name == 'RETURN':
                has_value = len(child.nodes) > 1 and child.nodes[1] is not None
                if func.return_type == 'void' and has_value:
                    raise RuntimeError(f"La función '{func.name}' de tipo 'void' no puede retornar un valor.")
                if func.return_type != 'void' and not has_value:
                    raise RuntimeError(f"La función '{func.name}' de tipo '{func.return_type}' debe retornar un valor, no void.")

                if has_value:
                    inferred = infer_value_type(local_storage, child.nodes[1])  # type: ignore
                    if inferred is not None:
                        validate_type(func.name, func.return_type, inferred, storage=local_storage)

                body_items.append(child)

            elif child.name == 'VAR_DECL':
                var_obj = visit_var(local_storage, child) # type: ignore
                if isinstance(var_obj, list):
                    body_items.extend(var_obj)
                else:
                    body_items.append(var_obj)

            elif child.name == 'VAR_ASSIGNATION':
                assign_obj = visit_assign(local_storage, child) # type: ignore
                body_items.append(assign_obj)

            elif child.name == 'WHILE':
                from core.processor.visitors.while_statement import visit_while
                while_obj = visit_while(local_storage, child, in_loop=True, is_nested=True)
                body_items.append(while_obj)

            elif child.name == 'FOR':
                from core.processor.visitors.for_statement import visit_for
                for_obj = visit_for(local_storage, child, is_nested=True)
                body_items.append(for_obj)

            elif child.name == 'IF':
                from core.processor.visitors.if_statement import visit_if
                if_obj = visit_if(local_storage, child, in_loop=False, is_nested=True)
                body_items.append(if_obj)

            elif child.name == 'CALL':
                from core.processor.visitors.call import visit_call
                call_obj = visit_call(local_storage, child)
                body_items.append(call_obj)

            elif child.name == 'MEMBER_CHAIN':
                from core.processor.visitors.call import visit_member_chain
                chain_obj = visit_member_chain(local_storage, child)
                body_items.append(chain_obj)

            elif child.name == 'INDEX_ACCESS':
                from core.processor.visitors.call import visit_index_access
                idx_obj = visit_index_access(local_storage, child)
                body_items.append(idx_obj)

            else:
                body_items.append(child)

    func.body = body_items
    return body_items


def visit_func(storage: Storage, node: ast.ASTRef) -> Function:
    # 1. Desempaquetar DECORATED_FUNCTION o FUNCTION

    if node.name == 'DECORATED_FUNCTION':
        decorators_node: ast.ASTRef | None = node.nodes[0]  # type: ignore
        func_node: ast.ASTRef = node.nodes[1]  # type: ignore
    else:
        decorators_node = None
        func_node = node

    # FUNCTION = Seq(FUNCTION_FIRM, FUNCTION_BODY)
    firm: ast.ASTRef = func_node.nodes[0]  # type: ignore
    body_node: ast.ASTRef = func_node.nodes[1]  # type: ignore

    # 2. Atributos base de la firma
    # firm.nodes: [Opt(privacy), Opt('__inline__'), SEGMENT_TYPE, IDENT, PARAMETERS, COLON]
    func_name: str = firm.nodes[-3].token.value  # type: ignore
    return_type: str = extract_type(firm.nodes[-4])  # type: ignore
    parameters_node: ast.ASTRef = firm.nodes[-2]  # type: ignore

    # Modificadores opcionales (privacy, __inline__)
    prefix_nodes = firm.nodes[:-4]
    privacy: str = storage.privacy
    is_inline: bool = False

    for item in prefix_nodes:
        if isinstance(item, ast.ASTTokenNode):
            val = item.token.value
            if val in ('public', 'private'):
                privacy = val
            elif val == '__inline__':
                is_inline = True

    if func_name in ('self', 'cls'):
        raise RuntimeError(f"No se puede usar el identificador reservado '{func_name}' como nombre de función.")

    from core.initiator.reserve_funnames import MagicFuncsManager

    if MagicFuncsManager.exists(func_name):
        raise RuntimeError(f"No se puede reemplazar la función intrínseca reservada '{func_name}'.")

    # 3. Verificación de colisiones en el Storage global
    storage.collition_name(func_name)

    # 4. Crear el objeto Function y registrarlo
    func = storage.add_function(
        name=func_name,
        return_type=return_type,
        parameters=[],
        body=[],
        privacy=privacy,
        is_inline=is_inline,
    )

    # 5. Crear el LocalStorage y asignarlo como scope de la función
    local_storage = LocalStorage(func, storage)
    func.scope = local_storage

    # 6. Procesar decoradores, parámetros y cuerpo
    process_decorators(storage, func, decorators_node)
    process_parameters(local_storage, func, parameters_node)
    process_body(local_storage, func, body_node)

    return func


__all__ = [
    'process_decorators',
    'process_parameters',
    'process_body',
    'visit_func',
]
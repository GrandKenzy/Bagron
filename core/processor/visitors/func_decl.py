import gram
from core.processor.objects import *
from core.processor.visitors import var_decl, if_statement

def _parse_param(param: gram.ASTNode) -> FunctionParam:
    tokens = getattr(param, 'tokens', [])
    is_variadic = any(getattr(t, 'token', None) == gram.Token.STAR or getattr(t, 'value', None) == '*' for t in tokens)
    vals = list(param.values)
    if len(vals) >= 2:
        param_type = str(vals[0])
        param_name = str(vals[1].value if hasattr(vals[1], 'value') else vals[1])
    elif len(vals) == 1:
        param_type = 'any' if is_variadic else 'void'
        param_name = str(vals[0].value if hasattr(vals[0], 'value') else vals[0])
    else:
        param_type = 'void'
        param_name = ''
    has_default = False
    default_val = None
    default_node = next((c for c in param.children if getattr(c, 'name', '') in ('EGL_VALUE', 'value', 'EGL_EXPRESSION', 'expression')), None)
    if default_node:
        has_default = True
        default_val = default_node.values[0] if default_node.values else None
    return FunctionParam(param_type, param_name, is_variadic, default_val, has_default)

def visit(node: gram.ASTNode):
    return_type, name = node.values[:2]
    params = []
    body = {}
    returned: Returned | None = None

    for child in node.children:
        if child.name in ('EGL_PARAMS', 'EC_PARAMS', 'ec_params'):
            for param in child.children:
                params.append(_parse_param(param))
        elif child.name in ('EGL_FUNC_BODY', 'EC_FUNC_BODY', 'func body'):
            for statement in child.children:
                if statement.name in ('EGL_STATEMENT', 'EC_STATEMENT', 'statement') and statement.children:
                    statement = statement.children[0]
                if statement.name in ('EGL_VAR_DECL', 'EC_VAR_DECL', 'var declaration'):
                    v = var_decl.visit(statement).ignore()
                    body[v] = 'Variable'
                elif statement.name in ('EGL_RETURN', 'EC_RETURN', 'return'):
                    ret_val = statement.values[1] if len(statement.values) > 1 else (statement.children[0].value if statement.children else None)
                    returned = Returned(ret_val).ignore()
                elif statement.name in ('EGL_IF_STATEMENT', 'IF_STATEMENT', 'if statement'):
                    v = if_statement.visit(statement)
                elif statement.name in ('EGL_PASS', 'pass'):
                    pass
                else:
                    print('falta por procesar', statement.name)

    if returned is None:
        return_nodes = node.find('EGL_RETURN') or node.find('EC_RETURN') or node.find('return')
        if return_nodes:
            stmt_node = return_nodes[0]
            ret_val = stmt_node.values[1] if len(stmt_node.values) > 1 else (stmt_node.children[0].value if stmt_node.children else None)
            returned = Returned(ret_val).ignore()

    func = Function(name, body, return_type, params, privacity='public').rescope()
    func.returned = returned
    return func
import gram
from core.processor.objects import ForStatement, Object
from core.processor.visitors.if_statement import _parse_stmt_node

def visit(node: gram.ASTNode, parent_scope: Object | None = None) -> ForStatement:
    var_name = str(node.values[1].value if hasattr(node.values[1], 'value') else node.values[1])
    mode = 'in'
    mode_node = node.find_first('EGL_LOOP_MODE')
    if mode_node:
        mode_vals = [str(v.value if hasattr(v, 'value') else v) for v in mode_node.values]
        if 'ran' in mode_vals:
            mode = 'ran'
        elif 'rand' in mode_vals:
            mode = 'rand'
        else:
            mode = 'in'
    elif len(node.values) > 2:
        val2 = str(node.values[2].value if hasattr(node.values[2], 'value') else node.values[2])
        if 'ran' in val2:
            mode = 'ran'
        elif 'rand' in val2:
            mode = 'rand'
    
    expr_targets = []
    body_stmts = []
    stmt_obj = ForStatement(var_name, mode, None, [], in_scope=parent_scope)

    for child in node.children:
        if child.name in ('EGL_LOOP_MODE', 'loop mode'):
            continue
        elif child.name in ('EGL_STMT_BODY', 'stmt body'):
            for sub in child.children:
                parsed = _parse_stmt_node(sub, stmt_obj)
                if parsed:
                    body_stmts.append(parsed)
        else:
            if child.values:
                expr_targets.append(list(child.values))

    stmt_obj.target = expr_targets if len(expr_targets) > 1 else (expr_targets[0] if expr_targets else None)
    stmt_obj.body = body_stmts
    return stmt_obj

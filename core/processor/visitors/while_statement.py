import gram
from core.processor.objects import WhileStatement, Object
from core.processor.visitors.if_statement import _parse_stmt_node

def visit(node: gram.ASTNode, parent_scope: Object | None = None) -> WhileStatement:
    cond_values = []
    body_stmts = []
    stmt_obj = WhileStatement([], [], in_scope=parent_scope)

    for child in node.children:
        if child.name in ('EGL_STMT_BODY', 'stmt body'):
            for sub in child.children:
                parsed = _parse_stmt_node(sub, stmt_obj)
                if parsed:
                    body_stmts.append(parsed)
        elif child.name in ('EGL_WHILE_COND', 'EGL_CONDITION', 'condition'):
            from core.processor.visitors.if_statement import parse_condition_node
            cond_values = parse_condition_node(child, stmt_obj)
        else:
            all_toks = getattr(child, 'all_tokens', None)
            if all_toks:
                cond_values = [getattr(t, 'value', t) for t in all_toks]
            elif child.values:
                cond_values.extend(list(child.values))

    if not cond_values and len(node.values) > 1:
        cond_values = list(node.values[1:])

    stmt_obj.condition = cond_values
    stmt_obj.body = body_stmts
    return stmt_obj

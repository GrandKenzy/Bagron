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
            from core.processor.visitors import expression as expr_visitor
            cond_values = expr_visitor.visit(child, stmt_obj)
        else:
            from core.processor.visitors import expression as expr_visitor
            cond_values = expr_visitor.visit(child, stmt_obj)

    if not cond_values and len(node.values) > 1:
        from core.processor.visitors import expression as expr_visitor
        cond_values = expr_visitor.visit(node.values[1], stmt_obj)

    stmt_obj.condition = cond_values
    stmt_obj.body = body_stmts
    return stmt_obj

import gram
from core.processor.objects import *
from core.processor.visitors.call import extract_call_args

def _parse_stmt_node(stmt_node: gram.ASTNode, parent_scope: Object) -> Object | None:
    if stmt_node.name in ('EGL_CALL', 'call'):
        name = stmt_node.values[0]
        args, kwargs = extract_call_args(stmt_node)
        return Call(name, args, kwargs, in_scope=parent_scope).ignore()
    elif stmt_node.name in ('EGL_METHOD_CALL', 'method call'):
        target = stmt_node.values[0]
        method = stmt_node.values[2] if len(stmt_node.values) >= 3 else stmt_node.values[1]
        args = list(stmt_node.children[0].values) if stmt_node.children else []
        return MethodCall(target, method, args, in_scope=parent_scope).ignore()
    elif stmt_node.name in ('EGL_ASSIGN', 'assign'):
        target = stmt_node.values[0]
        val = stmt_node.children[0].values[0] if stmt_node.children and stmt_node.children[0].values else None
        return Assign(target, val, in_scope=parent_scope).ignore()
    elif stmt_node.name in ('EGL_VAR_DECL', 'EC_VAR_DECL', 'var declaration'):
        from core.processor.visitors import var_decl
        v = var_decl.visit(stmt_node).ignore()
        v.in_scope = parent_scope
        return v
    elif stmt_node.name in ('EGL_FOR_STATEMENT', 'for statement'):
        from core.processor.visitors import for_statement
        return for_statement.visit(stmt_node, parent_scope).ignore()
    elif stmt_node.name in ('EGL_IF_STATEMENT', 'if statement'):
        stmt = visit(stmt_node).ignore()
        stmt.in_scope = parent_scope
        return stmt
    return None

def visit(node: gram.ASTNode) -> IfStatement:
    cond_values = []
    body_stmts = []
    else_stmts = []

    stmt_obj = IfStatement([], [], [])

    for child in node.children:
        if child.name in ('EGL_CONDITION', 'condition'):
            cond_values = list(child.values)
        elif child.name in ('EGL_STMT_BODY', 'stmt body'):
            for sub in child.children:
                parsed = _parse_stmt_node(sub, stmt_obj)
                if parsed:
                    body_stmts.append(parsed)
        elif child.name in ('EGL_ELSE_STATEMENT', 'else statement'):
            for else_child in child.children:
                if else_child.name in ('EGL_STMT_BODY', 'stmt body'):
                    for sub in else_child.children:
                        parsed = _parse_stmt_node(sub, stmt_obj)
                        if parsed:
                            else_stmts.append(parsed)

    stmt_obj.condition = cond_values
    stmt_obj.body = body_stmts
    stmt_obj.else_body = else_stmts
    return stmt_obj
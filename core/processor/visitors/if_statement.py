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
        args, _ = extract_call_args(stmt_node)
        return MethodCall(target, method, args, in_scope=parent_scope).ignore()
    elif stmt_node.name in ('EGL_ASSIGN', 'assign'):
        toks = [str(t.value if hasattr(t, 'value') else t) for t in getattr(stmt_node, 'all_tokens', [])]
        eq_idx = toks.index('=') if '=' in toks else -1
        idx_nodes = stmt_node.find('EGL_INDEX_ACCESS')
        if idx_nodes:
            target = f'{toks[0]}[{toks[1]}]' if eq_idx > 1 else stmt_node.values[0]
        else:
            target = stmt_node.values[0]

        val_nodes = stmt_node.find('EGL_VALUE')
        if eq_idx != -1 and len(toks) > eq_idx + 2:
            val = ' '.join(toks[eq_idx + 1:])
        elif val_nodes and val_nodes[0].values:
            val = val_nodes[0].values[0]
        else:
            val = toks[-1] if toks else None
        return Assign(target, val, in_scope=parent_scope).ignore()
    elif stmt_node.name in ('EGL_VAR_DECL', 'EC_VAR_DECL', 'var declaration'):
        from core.processor.visitors import var_decl
        v = var_decl.visit(stmt_node).ignore()
        v.in_scope = parent_scope
        return v
    elif stmt_node.name in ('EGL_FOR_STATEMENT', 'for statement'):
        from core.processor.visitors import for_statement
        return for_statement.visit(stmt_node, parent_scope).ignore()
    elif stmt_node.name in ('EGL_WHILE_STATEMENT', 'while statement'):
        from core.processor.visitors import while_statement
        return while_statement.visit(stmt_node, parent_scope).ignore()
    elif stmt_node.name in ('EGL_IF_STATEMENT', 'if statement'):
        stmt = visit(stmt_node).ignore()
        stmt.in_scope = parent_scope
        return stmt
    return None

def parse_condition_node(cond_node: gram.ASTNode, parent_scope: Object) -> list[Any]:
    calls = cond_node.find('EGL_CALL') + cond_node.find('EGL_METHOD_CALL')
    if calls:
        call_obj = _parse_stmt_node(calls[0], parent_scope)
        toks = [str(getattr(t, 'value', t)) for t in getattr(cond_node, 'all_tokens', cond_node.values)]
        ops = ['==', '!=', '<=', '>=', '<', '>']
        found_op = None
        for op in ops:
            if op in toks:
                found_op = op
                break
        if found_op:
            op_idx = toks.index(found_op)
            rhs = ' '.join(toks[op_idx + 1:])
            return [call_obj, found_op, rhs]
        if 'not' in toks:
            return ['not', call_obj]
        return [call_obj]
    if cond_node.values:
        return list(cond_node.values)
    toks = [str(getattr(t, 'value', t)) for t in getattr(cond_node, 'all_tokens', [])]
    return toks

def visit(node: gram.ASTNode) -> IfStatement:
    cond_values = []
    body_stmts = []
    else_stmts = []

    stmt_obj = IfStatement([], [], [])

    for child in node.children:
        if child.name in ('EGL_CONDITION', 'condition'):
            cond_values = parse_condition_node(child, stmt_obj)
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
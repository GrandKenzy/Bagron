import gram
from core.processor.objects import *
from core.processor.visitors import var_decl, if_statement
from core.processor.visitors.call import extract_call_args

def _parse_param(param: gram.ASTNode) -> FunctionParam:
    tokens = getattr(param, 'tokens', [])
    is_variadic = any(getattr(t, 'token', None) == gram.Token.STAR or getattr(t, 'value', None) == '*' for t in tokens)
    vals = list(param.values)
    spec_nodes = param.find('EGL_TYPE_SPEC')
    param_type = None
    if spec_nodes and spec_nodes[0].values:
        spec_vals = [str(v.value if hasattr(v, 'value') else v) for v in spec_nodes[0].values]
        if spec_vals[0] == '__void_p_t__' and len(spec_vals) > 1:
            param_type = f'{spec_vals[1]}*'
        else:
            param_type = spec_vals[0]
            if '*' in spec_vals:
                param_type = f'{param_type}*'
    
    if param_type:
        param_name = str(vals[-1].value if hasattr(vals[-1], 'value') else vals[-1]) if vals else ''
    elif len(vals) >= 2:
        param_type = str(vals[0])
        param_name = str(vals[1].value if hasattr(vals[1], 'value') else vals[1])
    elif len(vals) == 1:
        v_str = str(vals[0].value if hasattr(vals[0], 'value') else vals[0])
        if v_str in ('self', 'this'):
            param_type = 'class'
            param_name = v_str
        else:
            param_type = 'any' if is_variadic else 'void'
            param_name = v_str
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

def parse_body_statements(statements: list[gram.ASTNode], is_inline: bool = False) -> tuple[dict[Object, str], Returned | None, Any]:
    body = {}
    returned = None
    inline_target = None
    for statement in statements:
        if statement.name in ('EGL_STATEMENT', 'EC_STATEMENT', 'statement') and statement.children:
            statement = statement.children[0]
        if statement.name in ('EGL_VAR_DECL', 'EC_VAR_DECL', 'var declaration'):
            v = var_decl.visit(statement).ignore()
            body[v] = 'Variable'
        elif statement.name in ('EGL_RETURN', 'EC_RETURN', 'return'):
            mc_nodes = statement.find('EGL_METHOD_CALL')
            c_nodes = statement.find('EGL_CALL')
            if mc_nodes:
                mc_node = mc_nodes[0]
                target = mc_node.values[0]
                method = mc_node.values[2] if len(mc_node.values) >= 3 else mc_node.values[1]
                args, _ = extract_call_args(mc_node)
                ret_val = MethodCall(target, method, args).ignore()
            elif c_nodes:
                c_node = c_nodes[0]
                c_name = c_node.values[0]
                args, kwargs = extract_call_args(c_node)
                ret_val = Call(c_name, args, kwargs).ignore()
            else:
                all_toks = [t for t in getattr(statement, 'all_tokens', []) if str(getattr(t, 'value', t)) != 'return']
                if len(all_toks) > 1:
                    ret_val = ' '.join(str(getattr(t, 'value', t)) for t in all_toks)
                elif len(all_toks) == 1:
                    tok = all_toks[0]
                    if getattr(tok, 'token', None) == gram.Token.IDENT or isinstance(tok, gram.Identifier):
                        ret_val = tok if isinstance(tok, gram.Identifier) else gram.Identifier(tok.value)
                    else:
                        ret_val = tok.value if hasattr(tok, 'value') else tok
                else:
                    ret_val = statement.values[1] if len(statement.values) > 1 else (statement.children[0].value if statement.children and hasattr(statement.children[0], 'value') else (statement.children[0].values[0] if statement.children and statement.children[0].values else None))
            returned = Returned(ret_val).ignore()
            if is_inline:
                inline_target = ret_val
        elif statement.name in ('EGL_IF_STATEMENT', 'IF_STATEMENT', 'if statement'):
            v = if_statement.visit(statement).ignore()
            body[v] = 'IfStatement'
        elif statement.name in ('EGL_FOR_STATEMENT', 'for statement'):
            from core.processor.visitors import for_statement
            v = for_statement.visit(statement).ignore()
            body[v] = 'ForStatement'
        elif statement.name in ('EGL_ASSIGN', 'assign'):
            val_nodes = statement.find('EGL_VALUE')
            toks = [str(getattr(t, 'value', t)) for t in getattr(statement, 'all_tokens', [])]
            eq_idx = toks.index('=') if '=' in toks else -1

            val = None
            if val_nodes:
                mc_nodes = val_nodes[0].find('EGL_METHOD_CALL')
                c_nodes = val_nodes[0].find('EGL_CALL')
                if mc_nodes:
                    mc_node = mc_nodes[0]
                    target_m = mc_node.values[0]
                    method_m = mc_node.values[2] if len(mc_node.values) >= 3 else mc_node.values[1]
                    args_m, _ = extract_call_args(mc_node)
                    val = MethodCall(target_m, method_m, args_m).ignore()
                elif c_nodes:
                    c_node = c_nodes[0]
                    c_name = c_node.values[0]
                    args_c, kwargs_c = extract_call_args(c_node)
                    val = Call(c_name, args_c, kwargs_c).ignore()
                elif val_nodes[0].find('EGL_INDEX_ACCESS'):
                    idx_rhs = val_nodes[0].find('EGL_INDEX_ACCESS')[0]
                    target_v = str(idx_rhs.values[0])
                    idx_c = idx_rhs.children[0] if idx_rhs.children else None
                    idx_e = ''.join(str(getattr(t, 'value', t)) for t in getattr(idx_c, 'all_tokens', idx_c.values)) if idx_c else ''
                    val = f'{target_v}[{idx_e}]'
                elif eq_idx != -1 and len(toks) > eq_idx + 2:
                    val = ''.join(toks[eq_idx + 1:])
                elif val_nodes[0].values:
                    val = val_nodes[0].values[0] if len(val_nodes[0].values) == 1 else (''.join(toks[eq_idx + 1:]) if eq_idx != -1 else val_nodes[0].values[0])

            lhs_idx_nodes = [n for n in statement.find('EGL_INDEX_ACCESS') if not val_nodes or n not in val_nodes[0].walk()]
            lhs_mems = [n for n in statement.find('EGL_MEMBER_ACCESS') if not val_nodes or n not in val_nodes[0].walk()]
            if lhs_idx_nodes:
                target_lhs = str(lhs_idx_nodes[0].values[0])
                idx_lc = lhs_idx_nodes[0].children[0] if lhs_idx_nodes[0].children else None
                idx_le = ''.join(str(getattr(t, 'value', t)) for t in getattr(idx_lc, 'all_tokens', idx_lc.values)) if idx_lc else ''
                target = f'{target_lhs}[{idx_le}]'
            elif lhs_mems:
                target = '.'.join(str(v.value if hasattr(v, 'value') else v) for v in lhs_mems[0].values)
            else:
                target = statement.values[0]
            v = Assign(target, val).ignore()
            body[v] = 'Assign'
        elif statement.name in ('EGL_METHOD_CALL', 'method call'):
            target = statement.values[0]
            method = statement.values[2] if len(statement.values) >= 3 else statement.values[1]
            args, _ = extract_call_args(statement)
            v = MethodCall(target, method, args).ignore()
            body[v] = 'MethodCall'
            if is_inline and not inline_target:
                inline_target = v
        elif statement.name in ('EGL_CALL', 'call'):
            call_name = statement.values[0]
            args, kwargs = extract_call_args(statement)
            v = Call(call_name, args, kwargs).ignore()
            body[v] = 'Call'
            if is_inline and not inline_target:
                inline_target = v
        elif statement.name in ('EGL_PASS', 'pass'):
            pass
    return body, returned, inline_target

def visit(node: gram.ASTNode):
    vals = list(node.values)
    is_inline = False
    if '__inline__' in vals:
        is_inline = True
        vals.remove('__inline__')
    privacy = 'public'
    if 'public' in vals:
        privacy = 'public'
        vals.remove('public')
    elif 'private' in vals:
        privacy = 'private'
        vals.remove('private')
    return_type, name = vals[:2]
    params = []
    body = {}
    returned: Returned | None = None
    inline_target = None

    for child in node.children:
        if child.name in ('EGL_PARAMS', 'EC_PARAMS', 'ec_params'):
            for param in child.children:
                params.append(_parse_param(param))
        elif child.name in ('EGL_FUNC_BODY', 'EC_FUNC_BODY', 'func body'):
            parsed_b, parsed_ret, parsed_inline = parse_body_statements(child.children, is_inline)
            body.update(parsed_b)
            if parsed_ret:
                returned = parsed_ret
            if parsed_inline:
                inline_target = parsed_inline

    if returned is None:
        return_nodes = node.find('EGL_RETURN') or node.find('EC_RETURN') or node.find('return')
        if return_nodes:
            stmt_node = return_nodes[0]
            mc_nodes = stmt_node.find('EGL_METHOD_CALL')
            c_nodes = stmt_node.find('EGL_CALL')
            if mc_nodes:
                mc_node = mc_nodes[0]
                target = mc_node.values[0]
                method = mc_node.values[2] if len(mc_node.values) >= 3 else mc_node.values[1]
                args, _ = extract_call_args(mc_node)
                ret_val = MethodCall(target, method, args).ignore()
            elif c_nodes:
                c_node = c_nodes[0]
                c_name = c_node.values[0]
                args, kwargs = extract_call_args(c_node)
                ret_val = Call(c_name, args, kwargs).ignore()
            else:
                ret_val = stmt_node.values[1] if len(stmt_node.values) > 1 else (stmt_node.children[0].value if stmt_node.children and hasattr(stmt_node.children[0], 'value') else (stmt_node.children[0].values[0] if stmt_node.children and stmt_node.children[0].values else None))
            returned = Returned(ret_val).ignore()
            if is_inline and not inline_target:
                inline_target = ret_val

    if is_inline and not inline_target and body:
        inline_target = list(body.keys())[0]

    func = Function(name, body, return_type, params, privacity=privacy, is_inline=is_inline, inline_target=inline_target).rescope()
    func.returned = returned
    return func
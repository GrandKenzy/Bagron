import gram
from core.processor.visitors import *
from core.processor import objects

def process(ast: gram.ASTProgram):
    for node in ast.walk(0):
        if node.name in ('EGL_VAR_DECL', 'var declaration'):
            var_decl.visit(node)
        elif node.name in ('EGL_TYPE_DECL', 'type declaration'):
            type_decl.visit(node)
        elif node.name in ('EGL_CLASS_DECL', 'class declaration'):
            class_decl.visit(node)
        elif node.name in ('EGL_FUNC_DECL', 'func declaration'):
            func_decl.visit(node)
        elif node.name in ('EGL_IF_STATEMENT', 'if statement'):
            if_statement.visit(node)
        elif node.name in ('EGL_FOR_STATEMENT', 'for statement'):
            for_statement.visit(node)
        elif node.name in ('EGL_METHOD_CALL', 'method call'):
            from core.externs.manager import manager
            target = node.values[0]
            method = node.values[2] if len(node.values) >= 3 else node.values[1]
            args, _ = call.extract_call_args(node)
            target_str = str(target.value if hasattr(target, 'value') else target)
            method_str = str(method.value if hasattr(method, 'value') else method)
            if manager.has_namespace(target_str):
                manager.validate_call(target_str, method_str, args)
            objects.MethodCall(target, method, args)
        elif node.name in ('EGL_MEMBER_ACCESS', 'member access'):
            target = node.values[0]
            member = node.values[2] if len(node.values) >= 3 else node.values[1]
            objects.MemberAccess(target, member)
        elif node.name in ('EGL_CALL', 'call'):
            name = node.values[0]
            args, kwargs = call.extract_call_args(node)
            objects.Call(name, args, kwargs)
        elif node.name in ('EGL_ASSIGN', 'assign'):
            val_nodes = node.find('EGL_VALUE')
            toks = [str(getattr(t, 'value', t)) for t in getattr(node, 'all_tokens', [])]
            eq_idx = toks.index('=') if '=' in toks else -1
            if val_nodes and val_nodes[0].find('EGL_INDEX_ACCESS'):
                idx_rhs = val_nodes[0].find('EGL_INDEX_ACCESS')[0]
                target_v = str(idx_rhs.values[0])
                idx_c = idx_rhs.children[0] if idx_rhs.children else None
                idx_e = ''.join(str(getattr(t, 'value', t)) for t in getattr(idx_c, 'all_tokens', idx_c.values)) if idx_c else ''
                val = f'{target_v}[{idx_e}]'
            elif eq_idx != -1 and len(toks) > eq_idx + 2:
                val = ''.join(toks[eq_idx + 1:])
            elif val_nodes and val_nodes[0].values:
                val = val_nodes[0].values[0] if len(val_nodes[0].values) == 1 else (''.join(toks[eq_idx + 1:]) if eq_idx != -1 else val_nodes[0].values[0])
            else:
                val = None
            lhs_idx_nodes = [n for n in node.find('EGL_INDEX_ACCESS') if not val_nodes or n not in val_nodes[0].walk()]
            if lhs_idx_nodes:
                target_lhs = str(lhs_idx_nodes[0].values[0])
                idx_lc = lhs_idx_nodes[0].children[0] if lhs_idx_nodes[0].children else None
                idx_le = ''.join(str(getattr(t, 'value', t)) for t in getattr(idx_lc, 'all_tokens', idx_lc.values)) if idx_lc else ''
                target = f'{target_lhs}[{idx_le}]'
            else:
                target = node.values[0]
            objects.Assign(target, val)
        elif node.name in ('EGL_CLAUSE', 'clause'):
            from core.externs.manager import manager
            if len(node.values) >= 3:
                key = str(node.values[1].value if hasattr(node.values[1], 'value') else node.values[1])
                val = str(node.values[2].value if hasattr(node.values[2], 'value') else node.values[2])
                if key.lower() == 'target':
                    manager.set_target(val)
        elif node.name in ('EGL_INCLUDE', 'include'):
            from core.externs.manager import manager
            if len(node.values) >= 2:
                header = str(node.values[1].value if hasattr(node.values[1], 'value') else node.values[1])
                alias = None
                if len(node.values) >= 4 and str(node.values[2]) == 'as':
                    alias = str(node.values[3].value if hasattr(node.values[3], 'value') else node.values[3])
                manager.load_include(header, alias)
        elif node.name in ('EGL_IMPORT', 'import', 'EGL_DECLARE', 'declare'):
            pass
        else:
            print('Falta por procesar nodo: ', node.name)
    return objects.get_items()
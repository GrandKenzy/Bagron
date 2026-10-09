import gram
from core.processor.visitors import *
from core.processor import objects

def process(ast: gram.ASTProgram):
    for node in ast.walk(0):
        if node.name in ('EGL_VAR_DECL', 'EC_VAR_DECL', 'var declaration'):
            var_decl.visit(node)
        elif node.name in ('EGL_FUNC_DECL', 'EC_FUNC_DECL', 'func declaration'):
            func_decl.visit(node)
        elif node.name in ('EGL_IF_STATEMENT', 'IF_STATEMENT', 'if statement'):
            if_statement.visit(node)
        elif node.name in ('EGL_FOR_STATEMENT', 'for statement'):
            for_statement.visit(node)
        elif node.name in ('EGL_METHOD_CALL', 'method call'):
            target = node.values[0]
            method = node.values[2] if len(node.values) >= 3 else node.values[1]
            args = list(node.children[0].values) if node.children else []
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
            target = node.values[0]
            val = node.children[0].values[0] if node.children and node.children[0].values else None
            objects.Assign(target, val)
        elif node.name in ('EGL_CLAUSE', 'clause'):
            pass
        else:
            print('Falta por procesar nodo: ', node.name)
    return objects.get_items()
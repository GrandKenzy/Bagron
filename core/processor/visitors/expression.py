import gram
from typing import Any
from core.processor.objects.base import Object
from core.processor.objects.expression import (
    BinaryExpr,
    UnaryExpr,
    LiteralExpr,
    VariableExpr,
    IndexAccess,
)
from core.processor.objects.call import Call
from core.processor.objects.method_call import MethodCall
from core.processor.objects.member_access import MemberAccess
from core.processor.visitors.call import extract_call_args

BINARY_RULES = (
    'EGL_EXPRESSION',
    'EGL_LOGICAL_AND',
    'EGL_BITWISE_OR',
    'EGL_BITWISE_XOR',
    'EGL_BITWISE_AND',
    'EGL_EQUALITY',
    'EGL_COMPARISON',
    'EGL_SHIFT',
    'EGL_ADDITIVE',
    'EGL_MULTIPLICATIVE',
    'EGL_POWER',
)

def visit(node: Any, parent_scope: Object | None = None) -> Any:
    if node is None:
        return LiteralExpr(None, 'null', in_scope=parent_scope).ignore()

    if isinstance(node, (BinaryExpr, UnaryExpr, LiteralExpr, VariableExpr, IndexAccess, Call, MethodCall, MemberAccess)):
        if parent_scope and not node.in_scope:
            node.in_scope = parent_scope
        return node

    if isinstance(node, bool):
        return LiteralExpr(node, 'bool', in_scope=parent_scope).ignore()

    if isinstance(node, (int, float)):
        return LiteralExpr(node, 'number', in_scope=parent_scope).ignore()

    if isinstance(node, str):
        str_val = node.strip()
        if str_val in ('Null', 'None', 'null', 'NULL'):
            return LiteralExpr(None, 'null', in_scope=parent_scope).ignore()
        if str_val.lower() == 'true':
            return LiteralExpr(True, 'bool', in_scope=parent_scope).ignore()
        if str_val.lower() == 'false':
            return LiteralExpr(False, 'bool', in_scope=parent_scope).ignore()
        if (str_val.startswith('"') and str_val.endswith('"')) or (str_val.startswith("'") and str_val.endswith("'")):
            return LiteralExpr(str_val[1:-1], 'string', in_scope=parent_scope).ignore()
        if str_val.isdigit() or (str_val.startswith('-') and str_val[1:].isdigit()):
            return LiteralExpr(int(str_val), 'number', in_scope=parent_scope).ignore()
        if str_val.startswith('&') and len(str_val) > 1:
            return UnaryExpr('&', visit(str_val[1:].strip(), parent_scope), in_scope=parent_scope).ignore()
        if str_val.startswith('*') and len(str_val) > 1:
            return UnaryExpr('*', visit(str_val[1:].strip(), parent_scope), in_scope=parent_scope).ignore()
        if str_val.startswith('!') and len(str_val) > 1:
            return UnaryExpr('!', visit(str_val[1:].strip(), parent_scope), in_scope=parent_scope).ignore()
        return VariableExpr(str_val, in_scope=parent_scope).ignore()

    if isinstance(node, gram.Identifier):
        return VariableExpr(str(node.value), in_scope=parent_scope).ignore()

    node_name = getattr(node, 'name', '')

    if node_name in ('EGL_VALUE', 'value', 'EGL_CONDITION', 'condition', 'EGL_WHILE_COND'):
        if hasattr(node, 'children') and node.children:
            return visit(node.children[0], parent_scope)
        if hasattr(node, 'values') and node.values:
            return visit(node.values[0], parent_scope)

    if node_name in ('EGL_CALL', 'call'):
        call_name = str(node.values[0].value if hasattr(node.values[0], 'value') else node.values[0])
        args, kwargs = extract_call_args(node)
        proc_args = [visit(a, parent_scope) for a in args]
        proc_kwargs = {k: visit(v, parent_scope) for k, v in kwargs.items()}
        return Call(call_name, proc_args, proc_kwargs, in_scope=parent_scope).ignore()

    if node_name in ('EGL_METHOD_CALL', 'method call'):
        target = str(node.values[0].value if hasattr(node.values[0], 'value') else node.values[0])
        method = str(node.values[2].value if len(node.values) >= 3 else (node.values[1].value if hasattr(node.values[1], 'value') else node.values[1]))
        args, _ = extract_call_args(node)
        proc_args = [visit(a, parent_scope) for a in args]
        return MethodCall(target, method, proc_args, in_scope=parent_scope).ignore()

    if node_name in ('EGL_MEMBER_ACCESS', 'member access'):
        m_vals = [str(getattr(v, 'value', v)) for v in getattr(node, 'values', [])]
        if len(m_vals) >= 2:
            target = m_vals[0]
            member = '.'.join(m_vals[1:])
            return MemberAccess(target, member, in_scope=parent_scope).ignore()
        elif len(m_vals) == 1:
            return VariableExpr(m_vals[0], in_scope=parent_scope).ignore()
        return VariableExpr('', in_scope=parent_scope).ignore()

    if node_name in ('EGL_INDEX_ACCESS', 'index access'):
        idx_nodes = [c for c in getattr(node, 'children', [])]
        target = node.values[0] if getattr(node, 'values', []) else ''
        idx_expr = visit(idx_nodes[0], parent_scope) if idx_nodes else 0
        return IndexAccess(target, idx_expr, in_scope=parent_scope).ignore()

    if node_name in BINARY_RULES:
        children = getattr(node, 'children', [])
        tokens = getattr(node, 'tokens', [])

        if not children and getattr(node, 'values', []):
            if len(node.values) > 1 and node_name == 'EGL_POWER':
                vals = list(node.values)
                op_toks = [t for t in tokens if getattr(t, 'token', None) == gram.Token.POW or str(getattr(t, 'value', t)) == '**']
                res = visit(vals[-1], parent_scope)
                for i in range(len(vals) - 2, -1, -1):
                    op_str = str(getattr(op_toks[min(i, len(op_toks) - 1)], 'value', '**')) if op_toks else '**'
                    left_obj = visit(vals[i], parent_scope)
                    res = BinaryExpr(left_obj, op_str, res, in_scope=parent_scope).ignore()
                return res
            return visit(node.values[0], parent_scope)

        if len(children) == 1:
            return visit(children[0], parent_scope)

        if len(children) > 1:
            if node_name == 'EGL_POWER':
                sub_exprs = [visit(c, parent_scope) for c in children]
                res = sub_exprs[-1]
                for i in range(len(tokens) - 1, -1, -1):
                    op_str = str(getattr(tokens[i], 'value', tokens[i]))
                    res = BinaryExpr(sub_exprs[i], op_str, res, in_scope=parent_scope).ignore()
                return res

            res = visit(children[0], parent_scope)
            for op_token, right_child in zip(tokens, children[1:]):
                op_str = str(getattr(op_token, 'value', op_token))
                right_obj = visit(right_child, parent_scope)
                res = BinaryExpr(res, op_str, right_obj, in_scope=parent_scope).ignore()
            return res

    if node_name == 'EGL_UNARY':
        tokens = getattr(node, 'tokens', [])
        children = getattr(node, 'children', [])
        if tokens:
            op_str = str(getattr(tokens[0], 'value', tokens[0]))
            if children:
                operand = visit(children[0], parent_scope)
            elif len(getattr(node, 'values', [])) > 1:
                operand = visit(node.values[-1], parent_scope)
            elif len(getattr(node, 'values', [])) == 1:
                operand = visit(node.values[0], parent_scope)
            elif len(tokens) > 1:
                operand = visit(tokens[-1].value if hasattr(tokens[-1], 'value') else tokens[-1], parent_scope)
            else:
                operand = None
            return UnaryExpr(op_str, operand, in_scope=parent_scope).ignore()
        if children:
            return visit(children[0], parent_scope)
        if getattr(node, 'values', []):
            return visit(node.values[0], parent_scope)

    if node_name == 'EGL_PRIMARY':
        children = getattr(node, 'children', [])
        if children:
            return visit(children[0], parent_scope)
        if getattr(node, 'values', []):
            return visit(node.values[0], parent_scope)

    if node_name == 'Number':
        val = node.values[0] if getattr(node, 'values', []) else getattr(node, 'value', 0)
        if isinstance(val, bool):
            return LiteralExpr(val, 'bool', in_scope=parent_scope).ignore()
        return LiteralExpr(val, 'number', in_scope=parent_scope).ignore()

    if node_name == 'String':
        val = node.values[0] if getattr(node, 'values', []) else getattr(node, 'value', '')
        return LiteralExpr(str(val), 'string', in_scope=parent_scope).ignore()

    if node_name == 'Char':
        val = node.values[0] if getattr(node, 'values', []) else getattr(node, 'value', '')
        return LiteralExpr(str(val), 'char', in_scope=parent_scope).ignore()

    if node_name == 'Bool':
        val = node.values[0] if getattr(node, 'values', []) else getattr(node, 'value', False)
        str_b = str(getattr(val, 'value', val)).lower()
        return LiteralExpr(str_b == 'true', 'bool', in_scope=parent_scope).ignore()

    if node_name == 'Null':
        return LiteralExpr(None, 'null', in_scope=parent_scope).ignore()

    if node_name in ('Identifier', 'IDENT'):
        val = node.values[0] if getattr(node, 'values', []) else getattr(node, 'value', '')
        return VariableExpr(str(getattr(val, 'value', val)), in_scope=parent_scope).ignore()

    if hasattr(node, 'children') and node.children:
        return visit(node.children[0], parent_scope)

    if hasattr(node, 'values') and node.values:
        return visit(node.values[0], parent_scope)

    all_toks = getattr(node, 'all_tokens', [])
    if all_toks:
        flat_str = ' '.join(str(getattr(t, 'value', t)) for t in all_toks)
        return VariableExpr(flat_str, in_scope=parent_scope).ignore()

    return LiteralExpr(None, 'null', in_scope=parent_scope).ignore()

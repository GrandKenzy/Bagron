import re
from typing import Any
import core.processor.objects as objects
from core.processor.objects import Function, MethodCall, Call
from core.backend.c.visitors.expression import format_expression

def find_inline_function(name: str) -> Function | None:
    clean_name = str(name.value if hasattr(name, 'value') else name)
    for item in objects.get_items():
        if isinstance(item, Function) and item.name == clean_name and item.is_inline:
            return item
    return None

def expand_inline_call(inline_func: Function, args: list, kwargs: dict | None = None, is_statement: bool = False, block: Any = None):
    from core.backend.c.deffunc import CompiledCall
    kwargs = kwargs or {}

    param_map = {}
    for idx, p in enumerate(inline_func.parameters):
        if idx < len(args):
            param_map[p.name] = format_expression(args[idx], block)
        elif kwargs and p.name in kwargs:
            param_map[p.name] = format_expression(kwargs[p.name], block)
        elif p.has_default:
            param_map[p.name] = format_expression(p.default, block)
        else:
            param_map[p.name] = ''

    def _subst_arg(a: Any) -> Any:
        cls_name = getattr(getattr(a, '__class__', None), '__name__', '')
        if cls_name == 'VariableExpr':
            if a.name in param_map:
                return param_map[a.name]
            return a.name
        if cls_name == 'LiteralExpr':
            return format_expression(a, block)
        if isinstance(a, str):
            res = a
            for p_name, p_val in param_map.items():
                res = re.sub(rf'(?<!\.)\b{re.escape(p_name)}\b', p_val, res)
            return res
        raw_a = getattr(a, 'value', a)
        if isinstance(raw_a, str):
            res = raw_a
            for p_name, p_val in param_map.items():
                res = re.sub(rf'(?<!\.)\b{re.escape(p_name)}\b', p_val, res)
            return res
        return format_expression(a, block)

    target = inline_func.inline_target
    target_type = param_map.get('Type') or param_map.get('type')

    if isinstance(target, MethodCall):
        from core.backend.c.visitors import method_call
        sub_args = [_subst_arg(a) for a in target.args]
        mc = MethodCall(target.target, target.method, sub_args).ignore()
        compiled = method_call.visit(mc, is_statement=is_statement, block=block)
        is_ptr = (inline_func.return_type == 'ptr' or getattr(mc, 'returntype', '') == 'ptr')
        return CompiledCall(inline_func.name, args, inline_func.return_type, is_ptr, target_type, compiled)

    if isinstance(target, Call):
        from core.backend.c.deffunc import deffunc
        sub_args = [_subst_arg(a) for a in target.args]
        return deffunc(target.name, sub_args, getattr(target, 'kwargs', {}), is_statement=is_statement, block=block)

    if hasattr(target, '__class__') and target.__class__.__name__ == 'VariableExpr':
        raw_expr = param_map.get(target.name, target.name)
    else:
        raw_expr = _subst_arg(target)
    compiled = format_expression(raw_expr, block)
    if is_statement:
        compiled = f'{compiled};'
    is_ptr = (inline_func.return_type == 'ptr')
    return CompiledCall(inline_func.name, args, inline_func.return_type, is_ptr, target_type, compiled)

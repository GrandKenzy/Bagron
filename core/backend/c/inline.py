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
            val = args[idx].value if hasattr(args[idx], 'value') else args[idx]
            param_map[p.name] = str(val)
        elif kwargs and p.name in kwargs:
            val = kwargs[p.name].value if hasattr(kwargs[p.name], 'value') else kwargs[p.name]
            param_map[p.name] = str(val)
        elif p.has_default:
            param_map[p.name] = str(p.default)
        else:
            param_map[p.name] = ''

    target = inline_func.inline_target
    target_type = param_map.get('Type') or param_map.get('type')

    if isinstance(target, MethodCall):
        from core.backend.c.visitors import method_call
        sub_args = []
        for a in target.args:
            raw_a = str(a.value if hasattr(a, 'value') else a)
            for p_name, p_val in param_map.items():
                raw_a = re.sub(rf'(?<!\.)\b{re.escape(p_name)}\b', p_val, raw_a)
            sub_args.append(raw_a)
        mc = MethodCall(target.target, target.method, sub_args).ignore()
        compiled = method_call.visit(mc, is_statement=is_statement, block=block)
        is_ptr = (inline_func.return_type == 'ptr' or getattr(mc, 'returntype', '') == 'ptr')
        return CompiledCall(inline_func.name, args, inline_func.return_type, is_ptr, target_type, compiled)

    if isinstance(target, Call):
        from core.backend.c.deffunc import deffunc
        sub_args = []
        for a in target.args:
            raw_a = str(a.value if hasattr(a, 'value') else a)
            for p_name, p_val in param_map.items():
                raw_a = re.sub(rf'(?<!\.)\b{re.escape(p_name)}\b', p_val, raw_a)
            sub_args.append(raw_a)
        return deffunc(target.name, sub_args, getattr(target, 'kwargs', {}), is_statement=is_statement, block=block)

    raw_expr = str(getattr(target, 'value', target))
    for p_name, p_val in param_map.items():
        raw_expr = re.sub(rf'(?<!\.)\b{re.escape(p_name)}\b', p_val, raw_expr)
    compiled = format_expression(raw_expr, block)
    if is_statement:
        compiled = f'{compiled};'
    is_ptr = (inline_func.return_type == 'ptr')
    return CompiledCall(inline_func.name, args, inline_func.return_type, is_ptr, target_type, compiled)

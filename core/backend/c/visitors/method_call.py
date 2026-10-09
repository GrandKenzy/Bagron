from typing import Any
from core.processor.objects import MethodCall, Function
from core.externs.manager import manager
from core.backend.c.visitors.variable import resolve_variable

from core.backend.c.visitors.expression import format_expression

def _format_arg(arg: Any, block: Function | None = None) -> str:
    return format_expression(arg, block)

def visit(item: MethodCall, is_statement: bool = False, block: Function | None = None) -> str:
    import core.backend.c as c_backend
    target_str = str(item.target.value if hasattr(item.target, 'value') else item.target)
    method_str = str(item.method.value if hasattr(item.method, 'value') else item.method)

    if manager.has_namespace(target_str):
        sym_info = manager.validate_call(target_str, method_str, item.args)
        header = manager.get_header_for_namespace(target_str)
        if header:
            c_backend.add_include(header)
        item.returntype = sym_info.get('return_type', 'void')
        c_name = sym_info.get('c_name', method_str)
        c_args = [_format_arg(a, block) for a in item.args]
        call_code = f'{c_name}({", ".join(c_args)})'
        compiled = f'{call_code};' if is_statement else call_code
        item.compiled = compiled
        return compiled
    else:
        c_args = [_format_arg(a, block) for a in item.args]
        call_code = f'{target_str}.{method_str}({", ".join(c_args)})'
        compiled = f'{call_code};' if is_statement else call_code
        item.compiled = compiled
        return compiled

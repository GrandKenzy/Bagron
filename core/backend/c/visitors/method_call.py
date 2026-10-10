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
        c_args = []
        params = sym_info.get('params', [])
        for idx, a in enumerate(item.args):
            fmt = _format_arg(a, block)
            if idx < len(params) and params[idx].get('type') in ('ptr', 'pointer'):
                if fmt.startswith('&') and not fmt.startswith('(void*)'):
                    fmt = f'(void*){fmt}'
            c_args.append(fmt)
        call_code = f'{c_name}({", ".join(c_args)})'
        compiled = f'{call_code};' if is_statement else call_code
        item.compiled = compiled
        return compiled
    else:
        from core.processor.type_system import CUSTOM_TYPES
        class_name = None
        self_arg = None
        if target_str in ('self', 'this'):
            if block and hasattr(block, 'name') and '_' in block.name:
                class_name = block.name.split('_', 1)[0]
                self_arg = 'self'
        else:
            resolved = resolve_variable(target_str, block)
            if resolved and resolved.type:
                t = resolved.type.rstrip('*')
                if t in CUSTOM_TYPES and CUSTOM_TYPES[t].get('is_class'):
                    class_name = CUSTOM_TYPES[t].get('c_type') or t
                    self_arg = target_str if (resolved.is_pointer or resolved.type.endswith('*')) else f'&{target_str}'
                else:
                    from core.processor import objects
                    for it in objects.get_items().keys():
                        if hasattr(it, '__class__') and it.__class__.__name__ == 'ClassDecl' and getattr(it, 'name', None) == t:
                            class_name = t
                            self_arg = target_str if (resolved.is_pointer or resolved.type.endswith('*')) else f'&{target_str}'
                            break

        if class_name and self_arg:
            c_args = [self_arg] + [_format_arg(a, block) for a in item.args]
            call_code = f'{class_name}_{method_str}({", ".join(c_args)})'
            compiled = f'{call_code};' if is_statement else call_code
            item.compiled = compiled
            return compiled

        c_args = [_format_arg(a, block) for a in item.args]
        call_code = f'{target_str}.{method_str}({", ".join(c_args)})'
        compiled = f'{call_code};' if is_statement else call_code
        item.compiled = compiled
        return compiled

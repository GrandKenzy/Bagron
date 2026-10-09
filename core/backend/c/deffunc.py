from typing import Any
from core.initiator import reserve_funnames
from core.backend.c.visitors.variable import convert_type, resolve_variable

class CompiledCall:
    def __init__(self, name: str, args: list, returntype: str, is_pointer: bool, target_type: str | None, compiled: str):
        self.name = name
        self.args = args
        self.returntype = returntype
        self.is_pointer = is_pointer
        self.target_type = target_type
        self.compiled = compiled

def _format_print_arg(arg: Any, block: Any = None) -> tuple[str, str]:
    raw_str = str(arg.value if hasattr(arg, 'value') else arg)
    if (raw_str.startswith('"') and raw_str.endswith('"')) or (raw_str.startswith("'") and raw_str.endswith("'")):
        clean_val = raw_str[1:-1]
        return '%s', f'"{clean_val}"'
    if isinstance(arg, bool):
        return '%s', ('"true"' if arg else '"false"')
    if isinstance(arg, int):
        return '%d', str(arg)
    if isinstance(arg, float):
        return '%f', str(arg)
    
    resolved = resolve_variable(raw_str, block)
    if resolved:
        resolved.uses += 1
        if resolved.is_pointer:
            base = resolved.pointer_base_type or 'int'
            spec = '%d' if 'int' in base else ('%f' if 'float' in base or 'double' in base else '%s')
            return spec, f'*{resolved.name}'
        spec = '%s' if resolved.type == 'str' else ('%d' if 'int' in resolved.type else '%f')
        return spec, resolved.name

    if raw_str.isdigit():
        return '%d', raw_str

    return '%s', f'"{raw_str}"'

def deffunc(name: str, args: list, kwargs: dict | None = None, is_statement: bool = False, block: Any = None) -> CompiledCall:
    import core.backend.c as c_backend
    if isinstance(kwargs, bool):
        is_statement = kwargs
        kwargs = None
    kwargs = kwargs or {}

    clean_name = str(name.value if hasattr(name, 'value') else name)
    reserved = reserve_funnames.get_items().get(clean_name)
    ret_type = reserved.returntype if reserved else 'void'
    is_ptr = (ret_type == 'ptr')
    target_type = None
    bound = reserved.bind_args(args, kwargs) if reserved else {}

    if clean_name == 'malloc':
        c_backend.add_include('<stdlib.h>')
        raw_type = str(bound.get('Type') if bound.get('Type') is not None else (args[0].value if hasattr(args[0], 'value') else args[0]) if len(args) > 0 else 'void')
        count = str(bound.get('size') if bound.get('size') is not None else (args[1].value if hasattr(args[1], 'value') else args[1]) if len(args) > 1 else '1')
        resolved_t = resolve_variable(raw_type, block)
        if resolved_t and resolved_t.type == 'type':
            resolved_t.uses += 1
            if resolved_t.value:
                raw_type = str(resolved_t.value)
            else:
                raw_type = resolved_t.name
        target_type = raw_type
        c_type = convert_type(raw_type)
        compiled = f'({c_type}*)malloc(sizeof({c_type}) * {count})'
        return CompiledCall(clean_name, args, 'ptr', True, target_type, compiled)

    if clean_name == 'free':
        c_backend.add_include('<stdlib.h>')
        target_raw = str(bound.get('ptr') if bound.get('ptr') is not None else (args[0].value if hasattr(args[0], 'value') else args[0]) if args else '')
        resolved = resolve_variable(target_raw, block)
        if resolved:
            resolved.uses += 1
            target = resolved.name
        else:
            target = target_raw
        compiled = f'free({target});' if is_statement else f'free({target})'
        return CompiledCall(clean_name, args, 'void', False, None, compiled)

    if clean_name == 'print':
        c_backend.add_include('<stdio.h>')
        values = bound.get('values', args) if reserved else args
        sep = bound.get('sep', ' ') if reserved else ' '
        specs = []
        c_args = []
        for a in values:
            spec, val = _format_print_arg(a, block)
            specs.append(spec)
            c_args.append(val)
        sep_str = str(sep)
        if (sep_str.startswith('"') and sep_str.endswith('"')) or (sep_str.startswith("'") and sep_str.endswith("'")):
            sep_str = sep_str[1:-1]
        fmt = sep_str.join(specs) + r'\n'
        args_part = (', ' + ', '.join(c_args)) if c_args else ''
        compiled = f'printf("{fmt}"{args_part});' if is_statement else f'printf("{fmt}"{args_part})'
        return CompiledCall(clean_name, args, 'void', False, None, compiled)

    if clean_name == '__size__':
        raw_type = str(bound.get('type') if bound.get('type') is not None else (args[0].value if hasattr(args[0], 'value') else args[0]) if args else 'int')
        resolved_t = resolve_variable(raw_type, block)
        if resolved_t and resolved_t.type == 'type':
            resolved_t.uses += 1
            if resolved_t.value:
                raw_type = str(resolved_t.value)
            else:
                raw_type = resolved_t.name
        c_type = convert_type(raw_type)
        compiled = f'sizeof({c_type})'
        return CompiledCall(clean_name, args, 'int', False, None, compiled)

    compiled_args = []
    if reserved and reserved.params:
        for p in reserved.params:
            if p.is_variadic:
                var_vals = bound.get(p.name, [])
                if isinstance(var_vals, list):
                    for a in var_vals:
                        a_str = str(a.value if hasattr(a, 'value') else a)
                        resolved = resolve_variable(a_str, block)
                        if resolved:
                            resolved.uses += 1
                            compiled_args.append(resolved.name)
                        else:
                            compiled_args.append(a_str)
            else:
                val = bound.get(p.name)
                if val is not None:
                    a_str = str(val.value if hasattr(val, 'value') else val)
                    resolved = resolve_variable(a_str, block)
                    if resolved:
                        resolved.uses += 1
                        compiled_args.append(resolved.name)
                    else:
                        compiled_args.append(a_str)
        for extra in bound.get('_extra_args', []):
            a_str = str(extra.value if hasattr(extra, 'value') else extra)
            resolved = resolve_variable(a_str, block)
            if resolved:
                resolved.uses += 1
                compiled_args.append(resolved.name)
            else:
                compiled_args.append(a_str)
    else:
        for a in args:
            a_str = str(a.value if hasattr(a, 'value') else a)
            resolved = resolve_variable(a_str, block)
            if resolved:
                resolved.uses += 1
                compiled_args.append(resolved.name)
            else:
                compiled_args.append(a_str)
    call_expr = f'{clean_name}({", ".join(compiled_args)})'
    compiled = (call_expr + ';') if is_statement else call_expr
    return CompiledCall(clean_name, args, ret_type, is_ptr, target_type, compiled)

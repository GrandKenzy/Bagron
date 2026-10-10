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
    from core.processor.type_system import get_format_specifier
    if arg is None:
        return '%p', 'NULL'
    raw_val = arg.value if hasattr(arg, 'value') else arg
    if raw_val is None:
        return '%p', 'NULL'
    raw_str = str(raw_val).strip()
    if raw_str in ('Null', 'None', 'null', 'NULL'):
        return '%p', 'NULL'
    if (raw_str.startswith('"') and raw_str.endswith('"')) or (raw_str.startswith("'") and raw_str.endswith("'")):
        clean_val = raw_str[1:-1]
        return '%s', f'"{clean_val}"'
    if isinstance(arg, bool):
        return '%s', ('"true"' if arg else '"false"')
    if isinstance(arg, int):
        return '%d', str(arg)
    if isinstance(arg, float):
        return '%f', str(arg)

    if '.' in raw_str:
        base_name, prop = raw_str.split('.', 1)
        base_resolved = resolve_variable(base_name.strip(), block)
        if base_resolved:
            if prop == 'type':
                base_resolved.uses += 1
                if getattr(base_resolved, 'type_args', None):
                    args_s = ', '.join(str(a) for a in base_resolved.type_args)
                    return '%s', f'"{base_resolved.type}[{args_s}]"'
                return '%s', f'"{base_resolved.type}"'
            if prop == 'ptr':
                base_resolved.uses += 1
                return '%p', f'(void*)&{base_resolved.name}'
            if prop == 'size':
                base_resolved.uses += 1
                from core.backend.c.visitors.variable import convert_type
                if getattr(base_resolved, 'fixed_size', None) and getattr(base_resolved, 'element_type', None):
                    return '%zu', f'sizeof({convert_type(base_resolved.element_type)}) * {base_resolved.fixed_size}'
                return '%zu', f'sizeof({convert_type(base_resolved.type)})'
            if prop == 'len' and getattr(base_resolved, 'fixed_size', None):
                base_resolved.uses += 1
                return '%d', str(base_resolved.fixed_size)
            if prop in ('__const__', 'const'):
                base_resolved.uses += 1
                return '%d', ('1' if base_resolved.is_constant else '0')
            if prop in ('__visibility__', 'visibility'):
                base_resolved.uses += 1
                return '%d', ('0' if base_resolved.privacity == 'private' else '1')
            if prop == 'value':
                raise Exception(f"Member '.value' of type '{base_resolved.type}' is private and not directly accessible")

    if '[' in raw_str and raw_str.endswith(']'):
        base_name, idx_part = raw_str[:-1].split('[', 1)
        base_resolved = resolve_variable(base_name.strip(), block)
        if base_resolved:
            base_resolved.uses += 1
            elem_type = getattr(base_resolved, 'element_type', None) or 'int'
            spec = get_format_specifier(elem_type)
            from core.backend.c.visitors.expression import format_expression
            fmt_idx = format_expression(idx_part, block)
            idx_val = f'{base_resolved.name}[{fmt_idx}]'
            from core.processor.type_system import resolve_c_type
            if resolve_c_type(elem_type) == '_Float16':
                idx_val = f'(double){idx_val}'
            return spec, idx_val

    resolved = resolve_variable(raw_str, block)
    if resolved:
        resolved.uses += 1
        if resolved.is_pointer:
            if resolved.type == 'ptr' or not resolved.pointer_base_type:
                return '%p', resolved.name
            base = resolved.pointer_base_type or 'int'
            spec = get_format_specifier(base)
            return spec, f'*{resolved.name}'
        from core.backend.c.visitors.variable import convert_type
        if resolved.type == 'chain' or (getattr(resolved, 'fixed_size', None) and convert_type(getattr(resolved, 'element_type', '')) == 'char'):
            spec = '%s'
        else:
            spec = get_format_specifier(resolved.type)
        arg_val = resolved.name
        from core.processor.type_system import resolve_c_type
        if resolve_c_type(resolved.type) == '_Float16':
            arg_val = f'(double){resolved.name}'
        return spec, arg_val

    if raw_str.isdigit():
        return '%d', raw_str

    from core.backend.c.visitors.expression import format_expression
    fmt_expr = format_expression(raw_str, block)
    if fmt_expr.startswith('"') and fmt_expr.endswith('"'):
        return '%s', fmt_expr
    return '%d', fmt_expr

def _format_call_arg(a: Any, block: Any = None) -> str:
    if a is None:
        return 'NULL'
    raw_val = a.value if hasattr(a, 'value') else a
    if raw_val is None:
        return 'NULL'
    a_str = str(raw_val).strip()
    if a_str in ('Null', 'None', 'null', 'NULL'):
        return 'NULL'
    resolved = resolve_variable(a_str, block)
    if resolved:
        resolved.uses += 1
        return resolved.name
    from core.backend.c.visitors.expression import format_expression
    return format_expression(a, block)

def deffunc(name: str, args: list, kwargs: dict | None = None, is_statement: bool = False, block: Any = None) -> CompiledCall:
    import core.backend.c as c_backend
    if isinstance(kwargs, bool):
        is_statement = kwargs
        kwargs = None
    kwargs = kwargs or {}

    clean_name = str(name.value if hasattr(name, 'value') else name)

    from core.backend.c.inline import find_inline_function, expand_inline_call
    inline_func = find_inline_function(clean_name)
    if inline_func:
        expanded = expand_inline_call(inline_func, args, kwargs, is_statement=is_statement, block=block)
        if expanded is not None:
            return expanded

    reserved = reserve_funnames.get_items().get(clean_name)
    ret_type = reserved.returntype if reserved else 'void'
    is_ptr = (ret_type == 'ptr')
    target_type = None
    bound = reserved.bind_args(args, kwargs) if reserved else {}

    if not reserved:
        from core.externs.manager import manager
        extern_sym = manager.find_backend_symbol(clean_name)
        if extern_sym:
            sym_info, header = extern_sym
            if header:
                c_backend.add_include(header)
            ret_type = sym_info.get('return_type', 'void')
            is_ptr = (ret_type == 'ptr' or sym_info.get('is_pointer', False))
            bound = manager.bind_args(sym_info, args, kwargs)

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
        return CompiledCall(clean_name, args, 'int', False, None, compiled)

    from core.processor.type_system import CUSTOM_TYPES
    is_class_ctor = False
    if clean_name in CUSTOM_TYPES and CUSTOM_TYPES[clean_name].get('is_class'):
        is_class_ctor = True

    target_class_decl = None
    from core.processor import objects
    for it in objects.get_items().keys():
        if hasattr(it, '__class__') and it.__class__.__name__ == 'ClassDecl':
            if getattr(it, 'name', None) == clean_name or f'{getattr(it, "name", None)}_create' == clean_name:
                target_class_decl = it
                break

    if target_class_decl or is_class_ctor:
        ctor_func = getattr(target_class_decl, 'constructor_func', None)
        if ctor_func and hasattr(ctor_func, 'parameters'):
            for p in ctor_func.parameters[len(args):]:
                if getattr(p, 'has_default', False) and getattr(p, 'default', None) is not None:
                    args.append(p.default)
        compiled_args = [_format_call_arg(a, block) for a in args]
        fn_to_call = clean_name if clean_name.endswith('_create') else f'{clean_name}_create'
        call_expr = f'{fn_to_call}({", ".join(compiled_args)})'
        compiled = (call_expr + ';') if is_statement else call_expr
        return CompiledCall(clean_name, args, clean_name, False, None, compiled)

    compiled_args = []
    if reserved and reserved.params:
        for p in reserved.params:
            if p.is_variadic:
                var_vals = bound.get(p.name, [])
                if isinstance(var_vals, list):
                    for a in var_vals:
                        compiled_args.append(_format_call_arg(a, block))
            else:
                val = bound.get(p.name)
                if val is not None:
                    compiled_args.append(_format_call_arg(val, block))
        for extra in bound.get('_extra_args', []):
            compiled_args.append(_format_call_arg(extra, block))
    else:
        for a in args:
            compiled_args.append(_format_call_arg(a, block))
    call_expr = f'{clean_name}({", ".join(compiled_args)})'
    compiled = (call_expr + ';') if is_statement else call_expr
    return CompiledCall(clean_name, args, ret_type, is_ptr, target_type, compiled)

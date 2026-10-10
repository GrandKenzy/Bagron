import re
from typing import Any
from core.initiator.keywords import TYPES
from core.processor.objects import Function
from core.backend.c.visitors.variable import convert_type, resolve_variable

def is_type_symbol(target: str, block: Function | None = None) -> bool:
    if target in TYPES:
        return True
    if block and hasattr(block, 'parameters'):
        for p in block.parameters:
            p_type = p[0] if isinstance(p, (list, tuple)) or hasattr(p, '__getitem__') else getattr(p, 'type', '')
            p_name = p[1] if isinstance(p, (list, tuple)) or hasattr(p, '__getitem__') else getattr(p, 'name', '')
            if p_name == target:
                return p_type == 'type'
    if block and hasattr(block, 'get_vars'):
        for v in block.get_vars():
            if v.name == target:
                return v.type == 'type'
    if target and target[0].isupper():
        return True
    return False

def _replace_size(match: re.Match, block: Function | None = None) -> str:
    target = match.group(1)
    if target in ('this', 'self'):
        return match.group(0)
    if is_type_symbol(target, block):
        return f'sizeof({convert_type(target)})'
    resolved = resolve_variable(target, block)
    if resolved:
        resolved.uses += 1
        if getattr(resolved, 'fixed_size', None) and getattr(resolved, 'element_type', None):
            return f'(sizeof({convert_type(resolved.element_type)}) * {resolved.fixed_size})'
        return f'sizeof({convert_type(resolved.type)})'
    return match.group(0)

def _replace_type(match: re.Match, block: Function | None = None) -> str:
    target = match.group(1)
    if target in ('this', 'self'):
        return match.group(0)
    resolved = resolve_variable(target, block)
    if resolved:
        resolved.uses += 1
        if getattr(resolved, 'type_args', None):
            args_str = ', '.join(str(a) for a in resolved.type_args)
            return f'"{resolved.type}[{args_str}]"'
        return f'"{resolved.type}"'
    return match.group(0)

def _replace_len(match: re.Match, block: Function | None = None) -> str:
    target = match.group(1)
    if target in ('this', 'self'):
        return match.group(0)
    resolved = resolve_variable(target, block)
    if resolved and getattr(resolved, 'fixed_size', None):
        resolved.uses += 1
        return str(resolved.fixed_size)
    return match.group(0)

def _replace_ptr(match: re.Match, block: Function | None = None) -> str:
    target = match.group(1)
    if target in ('this', 'self'):
        return match.group(0)
    resolved = resolve_variable(target, block)
    if resolved:
        resolved.uses += 1
        return f'&{resolved.name}'
    return match.group(0)

def _replace_const(match: re.Match, block: Function | None = None) -> str:
    target = match.group(1)
    if target in ('this', 'self'):
        return match.group(0)
    resolved = resolve_variable(target, block)
    if resolved:
        resolved.uses += 1
        return '1' if resolved.is_constant else '0'
    return '1' if target.strip('_').isupper() else '0'

def _replace_visibility(match: re.Match, block: Function | None = None) -> str:
    target = match.group(1)
    if target in ('this', 'self'):
        return match.group(0)
    resolved = resolve_variable(target, block)
    if resolved:
        resolved.uses += 1
        return '0' if resolved.privacity == 'private' else '1'
    return '1'

def _check_value_access(match: re.Match, block: Function | None = None) -> str:
    target = match.group(1)
    if target in ('this', 'self'):
        return match.group(0)
    resolved = resolve_variable(target, block)
    if resolved:
        raise Exception(f"Member '.value' of type '{resolved.type}' is private and not directly accessible")
    return match.group(0)

def format_expression(raw: Any, block: Function | None = None) -> str:
    if raw is None:
        return 'NULL'
    raw_val = raw.value if hasattr(raw, 'value') else raw
    if hasattr(raw_val, '__class__') and raw_val.__class__.__name__ == 'MethodCall':
        from core.backend.c.visitors import method_call
        return method_call.visit(raw_val, is_statement=False, block=block)
    if hasattr(raw_val, '__class__') and raw_val.__class__.__name__ == 'Call':
        from core.backend.c.deffunc import deffunc
        compiled_call = deffunc(raw_val.name, raw_val.args, getattr(raw_val, 'kwargs', {}), is_statement=False, block=block)
        return compiled_call.compiled
    if raw_val is None:
        return 'NULL'
    str_raw = str(raw_val).strip()
    if str_raw in ('Null', 'None', 'null', 'NULL'):
        return 'NULL'
    if str_raw == '__fronted__':
        return '""'
    if (str_raw.startswith('"') and str_raw.endswith('"')) or (str_raw.startswith("'") and str_raw.endswith("'")):
        return str_raw
    if str_raw.startswith(('this.', 'self.')):
        return str_raw.replace('self.', 'self->').replace('this.', 'this->')
    str_raw = re.sub(r'\bself\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)', r'self->\1', str_raw)
    str_raw = re.sub(r'\bthis\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)', r'this->\1', str_raw)
    if str_raw.isdigit() or (str_raw.startswith('-') and str_raw[1:].isdigit()):
        return str_raw
    if str_raw.lower() in ('true', 'false'):
        return str_raw.lower()

    transformed = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\.type\b', lambda m: _replace_type(m, block), str_raw)
    transformed = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\.ptr\b', lambda m: _replace_ptr(m, block), transformed)
    transformed = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\.value\b', lambda m: _check_value_access(m, block), transformed)
    transformed = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\.size\b', lambda m: _replace_size(m, block), transformed)
    transformed = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\.len\b', lambda m: _replace_len(m, block), transformed)
    transformed = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\.(?:__const__|const)\b', lambda m: _replace_const(m, block), transformed)
    transformed = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\.(?:__visibility__|visibility)\b', lambda m: _replace_visibility(m, block), transformed)
    transformed = re.sub(r'\b(Null|None)\b', 'NULL', transformed)

    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', transformed):
        if transformed in ('NULL', 'true', 'false'):
            return transformed
        resolved = resolve_variable(transformed, block)
        if resolved:
            resolved.uses += 1
            return resolved.name

    for var in (block.get_vars() if block and hasattr(block, 'get_vars') else []):
        if re.search(rf'\b{re.escape(var.name)}\b', transformed):
            var.uses += 1

    return transformed

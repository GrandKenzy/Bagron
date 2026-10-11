import re
from typing import Any
from core.initiator.keywords import TYPES
from core.processor.objects import Function
from core.backend.c.visitors.variable import convert_type, resolve_variable

def is_type_symbol(target: str, block: Function | None = None) -> bool:
    from core.processor.type_system import CUSTOM_TYPES
    if target in TYPES or target in CUSTOM_TYPES:
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
        from core.processor.type_system import CUSTOM_TYPES
        type_info = CUSTOM_TYPES.get(resolved.type)
        if type_info and (type_info.get('is_class') or type_info.get('slots') or str(type_info.get('c_type', '')).startswith('inmodule_')):
            return match.group(0)
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
        from core.processor.type_system import CUSTOM_TYPES
        type_info = CUSTOM_TYPES.get(resolved.type)
        if type_info and type_info.get('is_class'):
            return match.group(0)
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

def _replace_enum_member(match: re.Match, block: Function | None = None) -> str:
    from core.processor.type_system import CUSTOM_TYPES
    full_target = match.group(1)
    member = match.group(2)
    short_target = full_target.split('.')[-1]
    for key in (full_target, short_target):
        type_info = CUSTOM_TYPES.get(key)
        if type_info and type_info.get('is_enum'):
            members = type_info.get('enum_members', {})
            if member in members:
                return str(members[member])
            c_base = type_info.get('c_type', short_target)
            return f'{c_base}_{member}'
    return match.group(0)

def format_expression(raw: Any, block: Function | None = None) -> str:
    if raw is None:
        return 'NULL'

    raw_cls = getattr(raw, '__class__', None)
    cls_name = getattr(raw_cls, '__name__', '')

    if cls_name == 'BinaryExpr':
        left_c = format_expression(raw.left, block)
        right_c = format_expression(raw.right, block)
        op = raw.op
        if op == 'and':
            op = '&&'
        elif op == 'or':
            op = '||'
        elif op == '//':
            op = '/'
        elif op == '**':
            import core.backend.c as c_backend
            c_backend.add_include('<math.h>')
            return f'pow({left_c}, {right_c})'
        return f'({left_c} {op} {right_c})'

    if cls_name == 'UnaryExpr':
        operand_c = format_expression(raw.operand, block)
        op = raw.op
        if op in ('not', 'NOT', '!'):
            return f'!({operand_c})'
        if op in ('&', '*'):
            return f'{op}{operand_c}'
        return f'{op}({operand_c})'

    if cls_name == 'LiteralExpr':
        if raw.value is None or raw.type == 'null':
            return 'NULL'
        if raw.type == 'bool' or isinstance(raw.value, bool):
            return 'true' if raw.value else 'false'
        if raw.type == 'string':
            from core.backend.c.visitors.function import _format_c_literal
            return _format_c_literal(raw.value, 'pstring')
        if raw.type == 'char':
            from core.backend.c.visitors.function import _format_c_literal
            return _format_c_literal(raw.value, 'char')
        return str(raw.value)

    if cls_name == 'VariableExpr':
        v_name = str(raw.name)
        if v_name in ('Null', 'None', 'null', 'NULL'):
            return 'NULL'
        if v_name.lower() in ('true', 'false'):
            return v_name.lower()
        if v_name == '__fronted__':
            return '""'
        if v_name in ('self', 'this'):
            return v_name
        if v_name.startswith(('self.', 'this.')):
            return v_name.replace('self.', 'self->').replace('this.', 'this->')
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', v_name):
            return format_expression(v_name, block)
        resolved = resolve_variable(v_name, block)
        if resolved:
            resolved.uses += 1
            return resolved.name
        return v_name

    if cls_name == 'IndexAccess':
        target_c = format_expression(raw.target, block)
        index_c = format_expression(raw.index, block)
        return f'{target_c}[{index_c}]'

    if cls_name == 'MemberAccess':
        target_str = format_expression(raw.target, block) if hasattr(raw.target, '__class__') and hasattr(raw.target, 'compiled') else str(getattr(raw.target, 'value', raw.target))
        member_str = str(getattr(raw.member, 'value', raw.member))
        if target_str in ('self', 'this'):
            return f'{target_str}->{member_str}'
        if member_str == 'type':
            class FakeMatch:
                def group(self, idx):
                    return target_str if idx == 1 else f'{target_str}.type'
            return _replace_type(FakeMatch(), block)
        if member_str == 'ptr':
            class FakeMatch:
                def group(self, idx):
                    return target_str if idx == 1 else f'{target_str}.ptr'
            return _replace_ptr(FakeMatch(), block)
        if member_str == 'size':
            class FakeMatch:
                def group(self, idx):
                    return target_str if idx == 1 else f'{target_str}.size'
            return _replace_size(FakeMatch(), block)
        if member_str == 'len':
            class FakeMatch:
                def group(self, idx):
                    return target_str if idx == 1 else f'{target_str}.len'
            return _replace_len(FakeMatch(), block)
        if member_str == 'const':
            class FakeMatch:
                def group(self, idx):
                    return target_str if idx == 1 else f'{target_str}.const'
            return _replace_const(FakeMatch(), block)
        if member_str == 'visibility':
            class FakeMatch:
                def group(self, idx):
                    return target_str if idx == 1 else f'{target_str}.visibility'
            return _replace_visibility(FakeMatch(), block)
        if member_str == 'value':
            class FakeMatch:
                def group(self, idx):
                    return target_str if idx == 1 else f'{target_str}.value'
            return _check_value_access(FakeMatch(), block)
        from core.processor.type_system import CUSTOM_TYPES
        for key in (target_str, target_str.split('.')[-1]):
            type_info = CUSTOM_TYPES.get(key)
            if type_info and type_info.get('is_enum'):
                members = type_info.get('enum_members', {})
                if member_str in members:
                    return str(members[member_str])
                c_base = type_info.get('c_type', key)
                return f'{c_base}_{member_str}'
        if not member_str:
            return target_str
        resolved = resolve_variable(target_str, block)
        if resolved:
            resolved.uses += 1
            if resolved.is_pointer or (resolved.type and resolved.type.endswith('*')):
                return f'{target_str}->{member_str}'
            return f'{target_str}.{member_str}'
        return f'{target_str}.{member_str}'

    if cls_name == 'MethodCall':
        from core.backend.c.visitors import method_call
        return method_call.visit(raw, is_statement=False, block=block)

    if cls_name == 'Call':
        from core.backend.c.deffunc import deffunc
        compiled_call = deffunc(raw.name, raw.args, getattr(raw, 'kwargs', {}), is_statement=False, block=block)
        return compiled_call.compiled

    if hasattr(raw, 'name') and hasattr(raw, 'values') and hasattr(raw, 'children'):
        from core.processor.visitors.expression import visit as visit_expr
        expr_obj = visit_expr(raw, block)
        return format_expression(expr_obj, block)

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
    transformed = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\.const\b', lambda m: _replace_const(m, block), transformed)
    transformed = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\.visibility\b', lambda m: _replace_visibility(m, block), transformed)
    transformed = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\.([A-Za-z_][A-Za-z0-9_]*)\b', lambda m: _replace_enum_member(m, block), transformed)
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

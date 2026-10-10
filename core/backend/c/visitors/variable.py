import re
import difflib
from core.processor.objects import *

most_similarity_comparison: str | None = None

def similarity(a: str, b: str) -> float:
    a = a.lower()
    b = b.lower()
    if a == b:
        return 1.0
    if len(a) == 0 or len(b) == 0:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()

def resolve_variable(name: Any, block: Function | None = None) -> Variable | None:
    str_name = str(name.value if hasattr(name, 'value') else name).strip()
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', str_name):
        return None
    if block and hasattr(block, 'parameters'):
        for p in block.parameters:
            p_name = p[1] if isinstance(p, (list, tuple)) or hasattr(p, '__getitem__') else getattr(p, 'name', '')
            if p_name == str_name:
                p_type = p[0] if isinstance(p, (list, tuple)) or hasattr(p, '__getitem__') else getattr(p, 'type', '')
                return Variable(p_name, p_name, p_type)
    if block and hasattr(block, 'get_vars'):
        for v in block.get_vars():
            if v.name == str_name:
                return v
    for v in get_vars():
        if v.name == str_name:
            return v
    return None

def check_variable_defined(variable: Variable, block: Function | None = None):
    global most_similarity_comparison
    most_similarity_comparison = None
    current_comparison = None
    current_similarity = 0.0
    
    if not variable.ref:
        return True

    value = variable.value

    if block:
        for param in block.parameters:
            sim = similarity(param[1], value)
            if sim > current_similarity:
                current_similarity = sim
                current_comparison = param[1]
            if param[1] == value:
                return param 
        else:
            for v in block.get_vars():
                sim = similarity(v.name, value)
                if sim > current_similarity:
                    current_similarity = sim
                    current_comparison = v.name
                if v.name == value:
                    v.uses += 1
                    return v

    for item in get_vars():
        sim = similarity(item.name, value)
        if sim > current_similarity:
            current_similarity = sim
            current_comparison = item.name
        if item.name == value:
            item.uses += 1
            return item
    
    if current_similarity > 0.5:
        most_similarity_comparison = current_comparison
    return False

def convert_type(type: str) -> str:
    from core.processor.type_system import resolve_c_type
    return resolve_c_type(type)

def is_enum_member(val_str: str) -> bool:
    from core.processor.type_system import CUSTOM_TYPES
    for t_info in CUSTOM_TYPES.values():
        if t_info.get('is_enum') and (val_str in t_info.get('enum_members', {}) or val_str in t_info.get('enum_members', {}).values()):
            return True
    return False

def type_is_compatible(value: int | float | str | bool, type: str) -> bool:
    if value is None:
        return True
    val_str = str(getattr(value, 'value', value)).strip()
    if val_str in ('Null', 'None', 'null', 'NULL'):
        return True
    c_type = convert_type(type)
    if 'int' in c_type:
        if isinstance(value, int) and not isinstance(value, bool):
            return True
        if is_enum_member(val_str):
            return True
        if val_str.isdigit() or (val_str.startswith('-') and val_str[1:].isdigit()):
            return True
        return False
    elif c_type in ('float', 'double', '_Float16'):
        if isinstance(value, (float, int)) and not isinstance(value, bool):
            return True
        if is_enum_member(val_str):
            return True
        try:
            float(val_str)
            return True
        except ValueError:
            return False
    elif c_type == 'char*':
        return isinstance(value, str)
    elif c_type == 'char':
        if isinstance(value, str):
            c_val = value.strip('\'"')
            if c_val in ('', '\\0', '\\n', '\\r', '\\t', '\\\\') or len(c_val) == 1:
                return True
            if value.startswith("'") and value.endswith("'"):
                return True
        return False
    elif c_type == 'bool':
        return isinstance(value, bool) or (isinstance(value, str) and value.lower() in ('true', 'false'))
    elif c_type in ('void*', 'ptr') or c_type.endswith('*'):
        return True
    return True

def same_type(ref: list[str] | Variable, type: str):
    if isinstance(ref, Variable):
        ref_type = ref.type
    else:
        ref_type = ref[0]

    state = convert_type(ref_type) == convert_type(type)
    if not state:
        if isinstance(ref, Variable):
            raise Exception(f'Variable {ref.name} is of type {ref.type}, but is being assigned a value of type {type}')
        else:
            raise Exception(f'Variable {ref[1]} is of type {ref[0]}, but is being assigned a value of type {type}')

def visit(variable: Variable, block: Function | None = None):
    if variable.type == 'type':
        variable.compiled = ''
        return

    if variable.name.startswith(('self.', 'this.')):
        arrow_target = variable.name.replace('self.', 'self->').replace('this.', 'this->')
        if hasattr(variable.value, '__class__') and variable.value.__class__.__name__ == 'Call':
            from core.backend.c.deffunc import deffunc
            compiled_call = deffunc(variable.value.name, variable.value.args, getattr(variable.value, 'kwargs', {}), is_statement=False, block=block)
            variable.value = compiled_call.compiled
        elif hasattr(variable.value, '__class__') and variable.value.__class__.__name__ == 'MethodCall':
            from core.backend.c.visitors import method_call
            compiled_call = method_call.visit(variable.value, is_statement=False, block=block)
            variable.value = compiled_call
        from core.backend.c.visitors.expression import format_expression
        val = format_expression(variable.value, block) if variable.value is not None else 'NULL'
        variable.compiled = f'{arrow_target} = {val};'
        return

    if hasattr(variable.value, '__class__') and variable.value.__class__.__name__ == 'Call':
        from core.backend.c.deffunc import deffunc
        compiled_call = deffunc(variable.value.name, variable.value.args, getattr(variable.value, 'kwargs', {}), is_statement=False, block=block)
        variable.value = compiled_call.compiled
        if compiled_call.is_pointer:
            variable.is_pointer = True
            if compiled_call.target_type:
                variable.pointer_base_type = compiled_call.target_type
    elif hasattr(variable.value, '__class__') and variable.value.__class__.__name__ == 'MethodCall':
        from core.backend.c.visitors import method_call
        ret_type = getattr(variable.value, 'returntype', 'void')
        compiled_call = method_call.visit(variable.value, is_statement=False, block=block)
        variable.value = compiled_call
        if ret_type == 'ptr' or variable.type == 'ptr':
            variable.is_pointer = True

    const_kw = 'const ' if variable.is_constant else ''
    static_kw = 'static ' if variable.privacity == 'private' else ''

    if variable.is_pointer or variable.type in ('ptr', '__void_p_t__', 'pointer'):
        base = variable.pointer_base_type or ('void' if variable.type in ('ptr', '__void_p_t__', 'pointer') else variable.type)
        t = f'{convert_type(base)}*'
        from core.backend.c.visitors.expression import format_expression
        val = format_expression(variable.value, block) if variable.value is not None else 'NULL'
        variable.compiled = f'{static_kw}{const_kw}{t} {variable.name} = {val};'
        return

    reference = None
    if variable.ref:
        reference = check_variable_defined(variable, block)
        if not reference:
            if get_most_similarity_comparison():
                raise Exception(f'Variable {variable.value} is not defined, did you mean "{get_most_similarity_comparison()}"?')
            else:
                raise Exception(f'Variable {variable.value} is not defined')

    t = convert_type(variable.type)
    
    value = variable.value
    from core.backend.c.visitors.expression import format_expression
    if value is None or str(getattr(value, 'value', value)).strip() in ('Null', 'None', 'null', 'NULL'):
        from core.processor.type_system import CUSTOM_TYPES
        if variable.type in CUSTOM_TYPES and CUSTOM_TYPES[variable.type].get('is_class'):
            value = '{0}'
        else:
            value = 'NULL'
    elif isinstance(value, str) and convert_type(variable.type) != 'char*':
        value = format_expression(value, block)

    if variable.type in ('pstring', 'chain') or convert_type(variable.type) == 'char*':
        val_clean = str(value).strip('\"\'')
        value = f'"{val_clean}"'
        if variable.fixed_size:
            variable.compiled = f'{static_kw}{const_kw}char {variable.name}[{variable.fixed_size}] = {value};'
            return
        variable.compiled = f'{static_kw}{const_kw}char* {variable.name} = {value};'
        return
    elif variable.type == 'array' or (variable.fixed_size and convert_type(variable.type) != 'char*'):
        elem_t = convert_type(getattr(variable, 'element_type', None) or 'int')
        if elem_t == 'char' and isinstance(value, str) and (value.startswith('"') or not value.startswith("'")):
            val_clean = str(value).strip('\"\'')
            if variable.value is not None:
                variable.compiled = f'{static_kw}{const_kw}char {variable.name}[{variable.fixed_size}] = "{val_clean}";'
            else:
                variable.compiled = f'{static_kw}{const_kw}char {variable.name}[{variable.fixed_size}];'
            return
        if variable.value is not None:
            init_val = format_expression(str(variable.value), block)
            variable.compiled = f'{static_kw}{const_kw}{elem_t} {variable.name}[{variable.fixed_size}] = {init_val};'
        else:
            variable.compiled = f'{static_kw}{const_kw}{elem_t} {variable.name}[{variable.fixed_size}];'
        return
    elif t == 'char':
        clean_c = str(value).strip('\'"')
        if not clean_c:
            value = "'\\0'"
        else:
            value = f"'{clean_c}'"
    elif t == 'bool':
        value = 'true' if (value is True or str(value).lower() == 'true') else 'false'
    
    is_expr = isinstance(value, str) and ('(' in value or '.' in value or '->' in value or '[' in value or value == 'NULL' or is_enum_member(value))
    if not reference and not is_expr and not type_is_compatible(value, t):
        raise Exception(f'Value {value} is not compatible with type {variable.type}')
    elif reference:
        same_type(reference, variable.type)

    variable.compiled = f'{static_kw}{const_kw}{t} {variable.name} = {value};'

def get_most_similarity_comparison():
    return most_similarity_comparison
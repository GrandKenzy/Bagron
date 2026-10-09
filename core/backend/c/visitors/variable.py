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
    str_name = str(name.value if hasattr(name, 'value') else name)
    if block and hasattr(block, 'get_vars'):
        for v in block.get_vars():
            if v.name == str_name:
                return v
    for v in get_vars():
        if v.name == str_name:
            return v
    best_match = None
    best_sim = 0.0
    for v in get_vars():
        sim = similarity(v.name, str_name)
        if sim > best_sim:
            best_sim = sim
            best_match = v
    if best_sim >= 0.5:
        return best_match
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
    if type == 'integer':
        return 'int'
    if type in ('int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64'):
        return f'{type}_t'
    elif type.startswith('i') and type[1:].isdigit():
        return f'int{type[1:]}_t'
    elif type.startswith('ui') and type[2:].isdigit():
        return f'uint{type[2:]}_t'
    elif type == 'str':
        return 'char*'
    elif type in ('bool', 'boolean'):
        return 'bool'
    else:
        return type

def type_is_compatible(value: int | float | str | bool, type: str) -> bool:
    if type in ['int', 'int8_t', 'int16_t', 'int32_t', 'int64_t', 'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t']:
        return isinstance(value, int) and not isinstance(value, bool)
    elif type in ['float', 'double']:
        return isinstance(value, float)
    elif type == 'str':
        return isinstance(value, str)
    elif type == 'char':
        return isinstance(value, str) and len(value.strip('\'')) == 1
    elif type == 'bool':
        return isinstance(value, bool) or (isinstance(value, str) and value.lower() in ('true', 'false'))
    else:
        return False

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

    if hasattr(variable.value, '__class__') and variable.value.__class__.__name__ == 'Call':
        from core.backend.c.deffunc import deffunc
        compiled_call = deffunc(variable.value.name, variable.value.args, getattr(variable.value, 'kwargs', {}), is_statement=False, block=block)
        variable.value = compiled_call.compiled
        if compiled_call.is_pointer:
            variable.is_pointer = True
            if compiled_call.target_type:
                variable.pointer_base_type = compiled_call.target_type

    if variable.is_pointer or variable.type == 'ptr':
        base = variable.pointer_base_type or 'void'
        t = f'{convert_type(base)}*'
        variable.compiled = f'{"static " if variable.privacity == "private" else ""}{t} {variable.name} = {variable.value};'
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
    if variable.type == 'str':
        val_clean = str(value).strip('\"\'')
        value = f'"{val_clean}"'
        if variable.fixed_size:
            variable.compiled = f'{"static " if variable.privacity == "private" else ""}char {variable.name}[{variable.fixed_size}] = {value};'
            return
        variable.compiled = f'{"static " if variable.privacity == "private" else ""}char* {variable.name} = {value};'
        return
    elif t == 'char':
        value = f"'{value}'"
    elif t == 'bool':
        value = 'true' if (value is True or str(value).lower() == 'true') else 'false'
    
    if not reference and not type_is_compatible(value, t):
        raise Exception(f'Value {value} is not compatible with type {variable.type}')
    elif reference:
        same_type(reference, variable.type)

    variable.compiled = f'{"static " if variable.privacity == "private" else ""}{t} {variable.name} = {value};'

def get_most_similarity_comparison():
    return most_similarity_comparison
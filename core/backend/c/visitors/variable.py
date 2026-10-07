
from core.processor.objects import *

most_similarity_comparison: str | None = None

def similarity(a: str, b: str) -> float:
    a = a.lower()
    b = b.lower()
    if a == b:
        return 1.0
    if len(a) == 0 or len(b) == 0:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    matches = 0
    for i in range(len(a)):
        if a[i] == b[i]:
            matches += 1
    return matches / len(b)


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
    if type == 'i8':
        return 'int8_t'
    elif type == 'i16':
        return 'int16_t'
    elif type == 'i32':
        return 'int32_t'
    elif type == 'i64':
        return 'int64_t'
    elif type == 'ui8':
        return 'uint8_t'
    elif type == 'ui16':
        return 'uint16_t'
    elif type == 'ui32':
        return 'uint32_t'
    elif type == 'ui64':
        return 'uint64_t'
    elif type == 'str':
        return 'char*'
    
    else:
        return type

def type_is_compatible(value: int | float | str, type: str) -> bool:
    if type in ['int', 'int8_t', 'int16_t', 'int32_t', 'int64_t', 'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t']:
        return isinstance(value, int)
    elif type in ['float', 'double']:
        return isinstance(value, float)
    elif type == 'str':
        return isinstance(value, str)
    elif type == 'char':
        return isinstance(value, str) and len(value.strip('\'')) == 1
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
    if t == 'char':
        value = f"'{value}'"
    elif t == 'str':
        value = f'"{value}"'
    
    if not reference and not type_is_compatible(value, t):
        raise Exception(f'Value {value} is not compatible with type {variable.type}')
    elif reference:
        same_type(reference, variable.type)

    variable.compiled = f'{'static ' if variable.privacity == "private" else ""}{t} {variable.name} = {value};'
    
    
def get_most_similarity_comparison():
    return most_similarity_comparison
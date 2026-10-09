from typing import Any
from core.processor.objects import Object, Variable, Function, Call, IfStatement, Assign

STDINT_TYPES = {
    'i8', 'i16', 'i32', 'i64',
    'ui8', 'ui16', 'ui32', 'ui64',
    'int8', 'int16', 'int32', 'int64',
    'uint8', 'uint16', 'uint32', 'uint64',
    'int8_t', 'int16_t', 'int32_t', 'int64_t',
    'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t',
}

STDBOOL_TYPES = {
    'bool',
    'boolean',
}

STDIO_SYMBOLS = {
    'print',
    'printf',
    'puts',
    'input',
    'scanf',
    'stdio',
}

STDLIB_SYMBOLS = {
    'malloc',
    'free',
    'calloc',
    'realloc',
    'exit',
    'abs',
    'rand',
    'srand',
}

def detect_stdint(type_name: str | None) -> bool:
    return bool(type_name and type_name in STDINT_TYPES)

def detect_stdbool(type_name: str | None, value: Any = None) -> bool:
    if type_name and type_name in STDBOOL_TYPES:
        return True
    if isinstance(value, bool):
        return True
    if isinstance(value, str) and value.lower() in ('true', 'false'):
        return True
    return False

def detect_stdio(symbol_name: str | None) -> bool:
    return bool(symbol_name and symbol_name in STDIO_SYMBOLS)

def detect_stdlib(symbol_name: str | None) -> bool:
    return bool(symbol_name and symbol_name in STDLIB_SYMBOLS)

def detect_from_variable(var: Variable) -> list[str]:
    headers: list[str] = []
    if detect_stdint(var.type) or (var.is_pointer and detect_stdint(var.pointer_base_type)):
        headers.append('<stdint.h>')
    if detect_stdbool(var.type, var.value):
        headers.append('<stdbool.h>')
    val_name = getattr(var.value, 'name', str(var.value)) if var.value is not None else ''
    if detect_stdio(var.name) or detect_stdio(val_name):
        headers.append('<stdio.h>')
    if detect_stdlib(val_name):
        headers.append('<stdlib.h>')
    return headers

def detect_from_function(func: Function) -> list[str]:
    headers: list[str] = []
    if detect_stdint(func.return_type):
        headers.append('<stdint.h>')
    if detect_stdbool(func.return_type):
        headers.append('<stdbool.h>')
    if detect_stdio(func.name):
        headers.append('<stdio.h>')
    if detect_stdlib(func.name):
        headers.append('<stdlib.h>')

    for param in func.parameters:
        param_type = param[0]
        if detect_stdint(param_type) and '<stdint.h>' not in headers:
            headers.append('<stdint.h>')
        if detect_stdbool(param_type) and '<stdbool.h>' not in headers:
            headers.append('<stdbool.h>')

    for body_item in func.body.keys():
        for h in detect_includes(body_item):
            if h not in headers:
                headers.append(h)

    return headers

def detect_from_call(call: Call) -> list[str]:
    headers: list[str] = []
    if detect_stdio(call.name):
        headers.append('<stdio.h>')
    if detect_stdlib(call.name):
        headers.append('<stdlib.h>')
    return headers

def detect_from_if(stmt: IfStatement) -> list[str]:
    headers: list[str] = []
    for item in stmt.body + stmt.else_body:
        for h in detect_includes(item):
            if h not in headers:
                headers.append(h)
    return headers

def detect_includes(item: Object) -> list[str]:
    if isinstance(item, Variable):
        return detect_from_variable(item)
    elif isinstance(item, Function):
        return detect_from_function(item)
    elif isinstance(item, Call):
        return detect_from_call(item)
    elif isinstance(item, IfStatement):
        return detect_from_if(item)
    return []

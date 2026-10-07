from typing import Callable

from core.processor.objects import *
from core.backend.c.visitors.variable import (
    Variable,
    check_variable_defined,
    convert_type,
    get_most_similarity_comparison,
    type_is_compatible,
)


def _format_c_literal(value: int | float | str, type: str) -> str:
    if type == 'char':
        if not isinstance(value, str):
            raise TypeError(f'El valor {value!r} no puede emitirse como literal char')
        escaped = value.translate(str.maketrans({
            '\\': '\\\\',
            "'": "\\'",
            '\n': '\\n',
            '\r': '\\r',
            '\t': '\\t',
            '\0': '\\0',
        }))
        return f"'{escaped}'"

    if type == 'str':
        if not isinstance(value, str):
            raise TypeError(f'El valor {value!r} no puede emitirse como literal str')
        escaped = value.translate(str.maketrans({
            '\\': '\\\\',
            '"': '\\"',
            '\n': '\\n',
            '\r': '\\r',
            '\t': '\\t',
            '\0': '\\0',
        }))
        return f'"{escaped}"'

    return str(value)

def visit(function: Function, processor: Callable):
    ret = function.returned


    rp: list[str] = []
    for param in function.parameters:
        if param[1] in rp:
            raise RuntimeError(f'Parámetros repetidos {param[1]}')
        rp.append(param[1])
        

    processor(function.body, function)
    
    returned = ""
    return_expression = ""
    
    if not ret and function.return_type != 'void':
        raise RuntimeError('Se prometió un retorno de tipo', function.return_type, 'pero no se encontró')
    
    if ret and ret.is_identifier():
        v = Variable('temp', ret.value, function.return_type).ignore()
        v.ref = True
        reference = check_variable_defined(v, function)
        if not reference:
            if get_most_similarity_comparison():
                raise Exception(f'Variable {v.value} is not defined, did you mean "{get_most_similarity_comparison()}"?')
            else:
                raise Exception(f'Variable {v.value} is not defined')
        
        if isinstance(reference, (list, tuple)):
            returned = reference[0]
        elif isinstance(reference, Variable):
            returned = reference.type
        else:
            raise TypeError(f'No se puede determinar el tipo de retorno de {ret.value!r}')

        return_expression = str(ret.value)
    elif ret:
        literal_is_compatible = (
            isinstance(ret.value, str) and len(ret.value) == 1
            if function.return_type == 'char'
            else type_is_compatible(ret.value, function.return_type)
        )
        if not literal_is_compatible:
            raise TypeError(
                f'El literal de retorno {ret.value!r} no es compatible con '
                f'el tipo {function.return_type!r} en {function.name}'
            )

        returned = function.return_type
        return_expression = _format_c_literal(ret.value, function.return_type)
    
    
    returned_c = convert_type(returned)
    type_c = convert_type(function.return_type)
    
    if returned_c != type_c:
        raise RuntimeError(f'Tipo de vuelta incompatible. Se retorna {returned_c} pero se esperaba {type_c} en {function.name}')
    
    params = ", ".join([' '.join(p) for p in function.parameters])
    
    
    
    header = f'{'static ' if function.privacity == 'private' else ''}{type_c} {function.name}({params}){{'
  
    body = ''
    
    for b in function.body.keys():
        if b.uses:
            body += f'\n    {b.compiled}'
  
    footer = f"\n    return {return_expression};\n}}" if ret else "\n}"
    
    
    function.compiled = header + body + footer
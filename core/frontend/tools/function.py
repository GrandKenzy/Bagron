from __future__ import annotations

from typing import TYPE_CHECKING

from core.frontend.objects import (
    FunctionSignature,
    FunctionSymbol,
    ParameterSpec,
    TypeSpec,
)
from core.frontend.tools.types import (
    INTEGER_TYPES,
    TypeResolutionError,
    UnsupportedExpressionError,
    ValueResolutionError,
    infer_call,
    infer_lvalue,
    infer_value,
    is_condition_type,
    is_compatible,
    resolve_type,
)
from core.frontend.tools.variable import build_symbol, collect_local
from gram import ast as gast

if TYPE_CHECKING:
    from core.compiler import Compiler


def _children(node: object) -> list[object]:
    if isinstance(node, list):
        return list(node)

    items = getattr(node, 'items', None)
    if items is not None:
        return list(items)

    nodes = getattr(node, 'nodes', None)
    if nodes is not None:
        return list(nodes)

    return []


def _token(node: object) -> object | None:
    return getattr(node, 'token', None)


def _token_kind(node: object) -> str | None:
    token = _token(node)
    token = getattr(token, 'token', token)
    return getattr(token, 'name', None)


def _token_value(node: object) -> object | None:
    token = _token(node)
    return getattr(token, 'value', None)


def _identifier(node: object) -> str | None:
    if _token_kind(node) == 'IDENT':
        return str(_token_value(node))

    for child in _children(node):
        found = _identifier(child)
        if found is not None:
            return found

    return None


def _declarator_info(node: gast.ASTRef) -> tuple[str, int, bool]:
    name = ''
    pointer_level = 0
    pointer_is_const = False

    for child in node.nodes:
        if isinstance(child, gast.ASTKeyword):
            pointer_is_const = child.token.value == 'const'
        elif isinstance(child, gast.ASTRef) and child.name == 'POINTER':
            pointer_level = len(child.nodes)
        elif _token_kind(child) == 'IDENT':
            name = str(_token_value(child))

    return name, pointer_level, pointer_is_const


def _signature_node(node: gast.ASTRef) -> gast.ASTRef | None:
    return next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef)
            and child.name == 'FUNCTION_SIGNATURE'
        ),
        None,
    )


def _body_node(node: gast.ASTRef) -> gast.ASTRef | None:
    return next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef)
            and child.name == 'FUNCTION_BODY'
        ),
        None,
    )


def _decorator_names(node: gast.ASTRef) -> tuple[str, ...]:
    decorators = next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef) and child.name == 'DECORATORS'
        ),
        None,
    )
    if decorators is None:
        return ()

    names: list[str] = []
    for decorator in _children(decorators):
        name = _identifier(decorator)
        if name is not None:
            names.append(name)
    return tuple(names)


def _parameter_items(parameters: gast.ASTRef) -> list[object]:
    if not parameters.nodes:
        return []
    return _children(parameters.nodes[0])


def _parameter_spec(pair: gast.ASTRef) -> ParameterSpec:
    declarator = pair.nodes[0]
    type_node = pair.nodes[2]
    name, pointer_level, pointer_is_const = _declarator_info(declarator)
    type_spec = resolve_type(
        type_node,
        pointer_level=pointer_level,
        pointer_is_const=pointer_is_const,
    )
    if type_spec.name == 'void' and type_spec.pointer_level == 0:
        raise TypeResolutionError(
            f'El parametro {name} no puede usar void por valor'
        )
    return ParameterSpec(
        name=name,
        type_spec=type_spec,
        has_default=len(pair.nodes) > 3,
    )


def signature_from_node(node: gast.ASTRef) -> tuple[str, FunctionSignature]:
    signature = _signature_node(node)
    if signature is None:
        raise TypeResolutionError('La funcion no contiene una firma valida')

    children = _children(signature)
    name = _identifier(signature) or ''
    parameter_index = next(
        (
            index for index, child in enumerate(children)
            if isinstance(child, gast.ASTRef)
            and child.name == 'PARAMETERS'
        ),
        None,
    )
    if parameter_index is None or parameter_index + 1 >= len(children):
        raise TypeResolutionError(f'La firma de {name or "<anonima>"} es invalida')

    parameters_node = children[parameter_index]
    parameters = tuple(
        _parameter_spec(pair)
        for pair in _parameter_items(parameters_node)
        if isinstance(pair, gast.ASTRef) and pair.name == 'PAIR_PARAM'
    )

    return_node = children[parameter_index + 1]
    return_pointer = 0
    for child in children[parameter_index + 2:]:
        if isinstance(child, gast.ASTRef) and child.name == 'POINTER':
            return_pointer = len(child.nodes)
            break

    return_type = resolve_type(return_node, pointer_level=return_pointer)
    if return_type.name == 'void' and return_type.array_depth:
        raise TypeResolutionError('void no puede usarse como array de retorno')

    return name, FunctionSignature(
        parameters=parameters,
        return_type=return_type,
    )


def _validate_bit_width(compiler: Compiler, name: str, type_spec: TypeSpec) -> None:
    if type_spec.bit_width is not None and type_spec.bit_width < 1:
        compiler.error(
            f'El ancho de {type_spec.canonical_name} debe ser mayor que cero: {name}'
        )


def _bind_parameters(compiler: Compiler, symbol: FunctionSymbol) -> None:
    scope = symbol.scope
    if scope is None:
        return

    for parameter in symbol.signature.parameters:
        if parameter.has_default:
            compiler.error(
                f'El parametro {parameter.name} de {symbol.name} no puede tener '
                'valor por defecto en esta fase'
            )

        _validate_bit_width(compiler, parameter.name, parameter.type_spec)
        if not parameter.name:
            compiler.error(f'La funcion {symbol.name} contiene un parametro sin nombre')
            continue
        if scope.contains_local(parameter.name):
            compiler.error(
                f'El parametro {parameter.name} esta duplicado en la funcion '
                f'{symbol.name}'
            )
            continue

        variable = build_symbol(
            scope,
            parameter.name,
            parameter.type_spec,
            kind='parameter',
        )
        scope.add(parameter.name, variable)


def collect(compiler: Compiler, nodes: list[gast.ASTRef]) -> None:
    """Register only top-level function signatures and parameter scopes."""
    for node in nodes:
        if node.name != 'FUNCTION':
            continue

        try:
            name, signature = signature_from_node(node)
        except TypeResolutionError as error:
            compiler.error(str(error))
            continue

        if not name:
            compiler.error('La funcion no tiene nombre')
            continue
        if name in compiler.storage.functions:
            compiler.error(f'La funcion ya fue declarada: {name}')
            continue

        decorators = _decorator_names(node)
        symbol = FunctionSymbol(name, signature, decorators=decorators)
        compiler.storage.define_function(symbol)
        compiler.function_bindings[id(node)] = symbol
        _validate_bit_width(compiler, name, signature.return_type)
        _bind_parameters(compiler, symbol)


def _return_value(node: gast.ASTRef) -> object | None:
    return next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
        ),
        None,
    )


def _validate_return(compiler: Compiler, symbol: FunctionSymbol, node: gast.ASTRef) -> None:
    scope = symbol.scope
    if scope is None:
        return

    value_node = _return_value(node)
    return_type = symbol.signature.return_type

    if (
        return_type.name == 'void'
        and return_type.pointer_level == 0
        and return_type.array_depth == 0
    ):
        if value_node is not None:
            compiler.error(f'La funcion {symbol.name} no puede retornar un valor')
        return

    if value_node is None:
        compiler.error(f'La funcion {symbol.name} debe retornar un valor')
        return

    try:
        value_info = infer_value(
            value_node,
            scope.resolve,
            compiler.storage.functions,
            current_function=symbol,
        )
    except UnsupportedExpressionError:
        return
    except ValueResolutionError as error:
        compiler.error(f'{symbol.name}: {error}')
        return

    if not is_compatible(return_type, value_info):
        compiler.error(
            f'El return de {symbol.name} no coincide con '
            f'{return_type.canonical_name}'
        )
        return

    if (
        value_info.address_origin == 'local'
        and value_info.type_spec.pointer_level > 0
        and not symbol.is_unsafe
    ):
        compiler.error(
            f'La funcion {symbol.name} no puede retornar la direccion de una '
            'variable local'
        )
        return

    symbol.return_values.append(value_info)
    symbol.return_node = value_node


def _for_binding(compiler: Compiler, symbol: FunctionSymbol, node: gast.ASTRef) -> None:
    scope = symbol.scope
    if scope is None:
        return

    signature = next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef) and child.name == 'FOR_SIGNATURE'
        ),
        None,
    )
    if signature is None:
        return

    children = _children(signature)
    name = ''
    type_node = None
    for index, child in enumerate(children):
        if _token_kind(child) == 'IDENT' and not name:
            name = str(_token_value(child))
        if _token_value(child) == ':':
            if index + 1 < len(children):
                type_node = children[index + 1]
            break

    if not name or type_node is None:
        return

    try:
        type_spec = resolve_type(type_node)
    except TypeResolutionError as error:
        compiler.error(f'{name}: {error}')
        return

    if (
        type_spec.name not in INTEGER_TYPES
        or type_spec.pointer_level
        or type_spec.array_depth
    ):
        compiler.error(
            f'El iterador {name} debe tener un tipo entero escalar especificado'
        )
        return

    range_values = [
        child for child in children
        if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
    ]
    if len(range_values) != 3:
        compiler.error(f'El rango de {name} debe tener start, end y step')
        return

    for index, value_node in enumerate(range_values):
        try:
            value_info = infer_value(
                value_node,
                scope.resolve,
                compiler.storage.functions,
                current_function=symbol,
            )
        except (UnsupportedExpressionError, ValueResolutionError) as error:
            compiler.error(f'El rango de {name} es invalido: {error}')
            continue
        if not is_compatible(type_spec, value_info):
            compiler.error(
                f'El valor {index + 1} del rango de {name} no coincide con '
                f'{type_spec.canonical_name}'
            )
        if index == 2 and value_info.is_literal and value_info.value == 0:
            compiler.error(f'El step de {name} no puede ser cero')

    if scope.contains_local(name):
        compiler.error(
            f'La variable {name} ya fue declarada en el scope {scope.scope_name}'
        )
        return

    scope.add(name, build_symbol(scope, name, type_spec, kind='local'))


def _condition_value(node: object) -> object | None:
    condition = next(
        (
            child for child in _children(node)
            if isinstance(child, gast.ASTRef) and child.name == 'CONDITION'
        ),
        None,
    )
    if condition is None:
        return None
    return next(
        (
            child for child in _children(condition)
            if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
        ),
        None,
    )


def _validate_condition(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: object,
) -> None:
    scope = symbol.scope
    if scope is None:
        return

    value_node = _condition_value(node)
    if value_node is None:
        compiler.error(f'La condicion de {symbol.name} es invalida')
        return

    try:
        value_info = infer_value(
            value_node,
            scope.resolve,
            compiler.storage.functions,
            current_function=symbol,
        )
    except (UnsupportedExpressionError, ValueResolutionError) as error:
        compiler.error(f'La condicion de {symbol.name} es invalida: {error}')
        return

    if not is_condition_type(value_info.type_spec):
        compiler.error(
            f'La condicion de {symbol.name} debe ser bool o entero escalar'
        )


_DEFINITION_NODES = {'CLASS', 'ENUM', 'FLAGS', 'MOLD', 'STRUCT', 'FUNCTION'}

_ASSIGNMENT_OPERATORS = {
    'ASSIGN': '=',
    'PLUS_ASSIGN': '+=',
    'MINUS_ASSIGN': '-=',
    'STAR_ASSIGN': '*=',
    'SLASH_ASSIGN': '/=',
    'PERCENT_ASSIGN': '%=',
    'AND_ASSIGN': '&=',
    'OR_ASSIGN': '|=',
    'XOR_ASSIGN': '^=',
    'SHL_ASSIGN': '<<=',
    'SHR_ASSIGN': '>>=',
}


def _assignment_target(node: gast.ASTRef) -> gast.ASTRef | None:
    return next(
        (
            child for child in _children(node)
            if isinstance(child, gast.ASTRef) and child.name == 'ASSIGN_TARGET'
        ),
        None,
    )


def _assignment_parts(
    node: gast.ASTRef,
) -> tuple[gast.ASTRef | None, str | None, object | None]:
    target = _assignment_target(node)
    operator = None
    value = next(
        (
            child for child in _children(node)
            if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
        ),
        None,
    )
    for child in _children(node):
        kind = _token_kind(child)
        if kind in _ASSIGNMENT_OPERATORS:
            operator = _ASSIGNMENT_OPERATORS[kind]
            break
    return target, operator, value


def _validate_assignment(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: gast.ASTRef,
) -> None:
    scope = symbol.scope
    if scope is None:
        return

    target, operator, value_node = _assignment_parts(node)
    name = _identifier(target) if target is not None else None
    variable = scope.namespace.get(name or '')
    try:
        target_info = infer_lvalue(
            target,
            scope.resolve,
            compiler.storage.functions,
            current_function=symbol,
        )
    except (UnsupportedExpressionError, ValueResolutionError) as error:
        compiler.error(f'{symbol.name}: {error}')
        return

    if variable is None and target_info.storage_origin != 'local':
        compiler.error(
            f'La asignacion de {symbol.name} requiere una variable local: '
            f'{name or "<anonima>"}'
        )
        return
    if variable is not None and (
        variable.value_is_const
        or (
            variable.type_spec.pointer_level > 0
            and variable.pointer_is_const
        )
    ):
        compiler.error(f'La variable constante no puede asignarse: {name}')
        return
    if target_info.type_spec.value_is_const:
        compiler.error(
            f'El valor apuntado por {name or "<anonimo>"} no puede asignarse'
        )
        return
    if operator is None or value_node is None:
        compiler.error(f'La asignacion de {symbol.name} es invalida')
        return

    try:
        value_info = infer_value(
            value_node,
            scope.resolve,
            compiler.storage.functions,
            current_function=symbol,
        )
    except (UnsupportedExpressionError, ValueResolutionError) as error:
        compiler.error(f'{symbol.name}: {error}')
        return

    if not is_compatible(target_info.type_spec, value_info):
        compiler.error(
            f'La asignacion de {name} no coincide con '
            f'{target_info.type_spec.canonical_name}'
        )
        return

    if operator != '=' and (
        target_info.type_spec.name not in INTEGER_TYPES
        or target_info.type_spec.pointer_level
        or target_info.type_spec.array_depth
    ):
        compiler.error(
            f'La asignacion {operator} solo admite enteros escalares: {name}'
        )
        return

    if (
        variable is not None
        and operator == '='
        and target_info.type_spec.pointer_level > 0
    ):
        # Pointer provenance is flow-sensitive at the declaration/assignment
        # level.  Unknown values remain unknown in safe functions and are
        # rejected only when a later operation dereferences them.
        variable.value_info = value_info


def _body_statements(body: gast.ASTRef) -> list[object]:
    statements: list[object] = []
    for child in _children(body):
        if isinstance(child, list):
            statements.extend(child)
        elif isinstance(child, (gast.ASTRef, gast.ASTKeyword)):
            statements.append(child)
    return statements


def _prep_count(compiler: Compiler, symbol: FunctionSymbol) -> int:
    return sum(
        block.function_name == symbol.name
        for block in getattr(compiler, 'prep_blocks', ())
    )


def _validate_assembler_body(
    compiler: Compiler,
    symbol: FunctionSymbol,
    body: gast.ASTRef,
) -> None:
    prep_count = _prep_count(compiler, symbol)
    if prep_count and not symbol.is_assembler:
        compiler.error(
            f'La funcion {symbol.name} requiere el decorador @assembler '
            'para contener ensamblador'
        )
        return

    if not symbol.is_assembler:
        return

    if prep_count > 1:
        compiler.error(
            f'La funcion @assembler {symbol.name} solo puede contener '
            'un bloque de ensamblador'
        )

    return_count = 0
    return_asm_count = 0
    pass_count = 0
    for statement in _body_statements(body):
        if isinstance(statement, gast.ASTKeyword):
            if _token_value(statement) == 'pass':
                pass_count += 1
                continue
            compiler.error(
                f'La funcion @assembler {symbol.name} solo puede contener '
                'ensamblador y return'
            )
            continue

        if isinstance(statement, gast.ASTRef) and statement.name == 'RETURN_ASM':
            return_asm_count += 1
            continue

        if isinstance(statement, gast.ASTRef) and statement.name == 'RETURN':
            return_count += 1
            continue

        compiler.error(
            f'La funcion @assembler {symbol.name} solo puede contener '
            'ensamblador y return'
        )

    if pass_count != prep_count:
        compiler.error(
            f'La funcion @assembler {symbol.name} solo puede contener '
            'un bloque de ensamblador opcional y return'
        )

    if prep_count:
        if return_count:
            compiler.error(
                f'La funcion @assembler {symbol.name} debe usar return asm '
                'cuando contiene ensamblador'
            )
        if return_asm_count != 1:
            compiler.error(
                f'La funcion @assembler {symbol.name} requiere un unico return asm'
            )
    elif return_asm_count:
        compiler.error(
            f'La funcion @assembler {symbol.name} no puede usar return asm '
            'sin un bloque de ensamblador'
        )

    if not prep_count and return_count != 1:
        compiler.error(
            f'La funcion @assembler {symbol.name} requiere un unico return'
        )


def _validate_return_asm(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: gast.ASTRef,
) -> None:
    if not symbol.is_assembler:
        compiler.error(
            f'La funcion {symbol.name} requiere el decorador @assembler para usar '
            'return asm'
        )
        return

    if symbol.signature.return_type.name != 'int' or (
        symbol.signature.return_type.pointer_level
        or symbol.signature.return_type.array_depth
    ):
        compiler.error(
            f'La funcion @assembler {symbol.name} debe retornar int'
        )
        return

    symbol.return_asm_node = node


def _process_body_node(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: object,
    returns: list[int],
    loop_depth: int = 0,
) -> None:
    if isinstance(node, gast.ASTKeyword):
        if _token_value(node) in {'break', 'continue'} and loop_depth == 0:
            compiler.error(
                f'{_token_value(node)} solo puede usarse dentro de un bucle'
            )
        return
    if isinstance(node, list):
        for child in node:
            _process_body_node(compiler, symbol, child, returns, loop_depth)
        return
    if not isinstance(node, gast.ASTRef):
        return

    if node.name in _DEFINITION_NODES:
        return
    if node.name == 'VAR':
        if symbol.scope is not None:
            collect_local(
                compiler,
                symbol.scope,
                node,
                current_function=symbol,
            )
        return
    if node.name == 'VAR_ASSIGNATION':
        _validate_assignment(compiler, symbol, node)
        return
    if node.name == 'RETURN':
        _validate_return(compiler, symbol, node)
        returns[0] += 1
        return
    if node.name == 'RETURN_ASM':
        _validate_return_asm(compiler, symbol, node)
        returns[0] += 1
        return
    if node.name == 'FOR':
        _for_binding(compiler, symbol, node)

    if node.name == 'CALL':
        try:
            infer_call(
                node,
                symbol.scope.resolve if symbol.scope is not None else {},
                compiler.storage.functions,
                current_function=symbol,
            )
        except (UnsupportedExpressionError, ValueResolutionError) as error:
            compiler.error(f'{symbol.name}: {error}')

    if node.name in {'IF_SIGNATURE', 'ELIF_SIGNATURE', 'WHILE_SIGNATURE'}:
        _validate_condition(compiler, symbol, node)

    if node.name in {'CALL', 'IF', 'WHILE'}:
        symbol.body_supported_for_entrypoint = False

    child_loop_depth = loop_depth + (node.name in {'FOR', 'WHILE'})
    for child in _children(node):
        _process_body_node(compiler, symbol, child, returns, child_loop_depth)


def process(compiler: Compiler, node: gast.ASTRef) -> None:
    """Collect local variables and validate returns for one top-level function."""
    symbol = compiler.function_bindings.get(id(node))
    if symbol is None:
        return

    body = _body_node(node)
    if body is None:
        compiler.error(f'La funcion {symbol.name} no tiene cuerpo')
        return

    symbol.body_node = body

    _validate_assembler_body(compiler, symbol, body)

    returns = [0]
    for child in _children(body):
        _process_body_node(compiler, symbol, child, returns)

    return_type = symbol.signature.return_type
    if returns[0] == 0:
        if return_type.name == 'void' and return_type.pointer_level == 0:
            compiler.error(
                f'La funcion void {symbol.name} debe terminar con return'
            )
        elif not (
            return_type.name == 'void'
            and return_type.pointer_level == 0
        ):
            compiler.error(f'La funcion {symbol.name} no tiene return')


__all__ = ['collect', 'process', 'signature_from_node']

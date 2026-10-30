from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from core.frontend.objects import (
    AggregateSymbol,
    FunctionSignature,
    FunctionSymbol,
    ParameterSpec,
    TypeSpec,
)
from core.frontend.tools.types import (
    FOR_ITERATOR_TYPES,
    INTEGER_TYPES,
    TypeResolutionError,
    UnsupportedExpressionError,
    ValueResolutionError,
    infer_call,
    infer_lvalue,
    infer_value,
    is_bool_scalar,
    is_buffer_type,
    is_condition_type,
    is_compatible,
    resolve_type,
    target_iteration_limit,
    _integer_bounds,
    _type_is_const,
    _type_is_unique,
    _type_name,
)
from core.frontend.tools.variable import build_symbol, collect_local
from core.frontend.handles.variables import handle_variable
from gram import ast as gast

from core.storage import Storage

if TYPE_CHECKING:
    from core.compiler import Compiler


_FUNCTION_DECORATORS = frozenset({'unsafe', 'assembler'})
_MAGIC_STATUS_METHODS = frozenset({'__ongetter__', '__onsetter__'})
_MAGIC_COMPARISON_METHODS = frozenset({'__eq__'})
_MAGIC_LIFECYCLE_METHODS = frozenset({'__deletion__'})
_MAGIC_BINARY_METHODS = frozenset({
    '__add__', '__sub__', '__mul__', '__div__', '__truediv__', '__mod__',
    '__and__', '__or__', '__xor__', '__shl__', '__shr__',
})
_MAGIC_UNARY_METHODS = frozenset({'__pos__', '__neg__'})
_MAGIC_METHODS = (
    _MAGIC_COMPARISON_METHODS
    | _MAGIC_STATUS_METHODS
    | _MAGIC_LIFECYCLE_METHODS
    | _MAGIC_BINARY_METHODS
    | _MAGIC_UNARY_METHODS
)


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


def _privacy(node: object) -> str:
    for child in _children(node):
        value = _token_value(child)
        if value in ('public', 'private'):
            return str(value)
        if isinstance(child, gast.ASTRef):
            found = _privacy(child)
            if found != 'public':
                return found
    return 'public'


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


def _global_declarations(node: object) -> list[gast.ASTRef]:
    """Collect ``global`` declarations from the complete function body."""
    if isinstance(node, gast.ASTRef) and node.name == 'GLOBAL':
        return [node]

    declarations: list[gast.ASTRef] = []
    for child in _children(node):
        declarations.extend(_global_declarations(child))
    return declarations


def _module_variable(compiler: Compiler, name: str) -> object | None:
    return compiler.storage.resolve_module_value(name)


def _register_global_declarations(
    compiler: Compiler,
    symbol: FunctionSymbol,
    body: gast.ASTRef,
) -> None:
    """Make module data visible only after an explicit source declaration."""
    scope = symbol.scope
    if scope is None:
        return

    seen: set[str] = set()
    for declaration in _global_declarations(body):
        name = _identifier(declaration)
        if not name:
            compiler.error(
                f'La declaracion global de {symbol.name} no contiene un nombre'
            )
            continue
        if name in seen:
            compiler.error(
                f'La variable global {name} fue declarada dos veces en '
                f'{symbol.name}'
            )
            continue
        seen.add(name)

        if name in symbol.local_variables or scope.contains_local(name):
            compiler.error(
                f'La variable global {name} entra en conflicto con un '
                f'parametro o local de {symbol.name}'
            )
            continue

        if _module_variable(compiler, name) is None:
            compiler.error(
                f'global {name} solo puede referirse a una variable de modulo '
                f'existente en {symbol.name}'
            )
            continue

        symbol.global_variables.add(name)
        scope.global_names.add(name)


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


def _contains_token_value(node: object, value: str) -> bool:
    if _token_value(node) == value:
        return True
    return any(_contains_token_value(child, value) for child in _children(node))


def _is_inline(node: gast.ASTRef) -> bool:
    signature = _signature_node(node)
    return signature is not None and _contains_token_value(signature, 'inline')


def _validate_decorators(
    compiler: Compiler,
    function_name: str,
    decorators: tuple[str, ...],
) -> None:
    seen: set[str] = set()
    for decorator in decorators:
        if decorator not in _FUNCTION_DECORATORS:
            compiler.error(
                f'El decorador @{decorator} no existe para la funcion '
                f'{function_name}'
            )
        elif decorator in seen:
            compiler.error(
                f'El decorador @{decorator} esta repetido en {function_name}'
            )
        seen.add(decorator)


def validate_magic_method_signature(
    compiler: Compiler,
    class_name: str,
    method_name: str,
    signature: FunctionSignature,
    decorators: tuple[str, ...],
) -> None:
    """Validate reserved signatures used by class magic methods.

    These methods remain ordinary class methods in the semantic model.  Their
    names only opt them into compiler-generated calls at the relevant access
    sites.
    """
    if method_name not in _MAGIC_METHODS:
        return

    if 'static' in decorators:
        compiler.error(
            f'El metodo magico {class_name}.{method_name} no puede ser @static'
        )

    parameters = signature.parameters
    visible = [
        parameter for parameter in parameters
        if not (
            parameter.is_length
            or parameter.is_size
            or parameter.is_region
            or parameter.is_receiver
        )
    ]
    return_type = signature.return_type

    if method_name in _MAGIC_STATUS_METHODS:
        length_parameters = [
            parameter for parameter in parameters if parameter.is_length
        ]
        valid_chain = (
            len(visible) == 1
            and visible[0].type_spec.name == 'chain'
            and visible[0].type_spec.pointer_level == 0
            and visible[0].type_spec.array_depth == 0
        )
        valid_length = (
            len(length_parameters) == 1
            and length_parameters[0].length_of == visible[0].name
            if visible
            else False
        )
        if not valid_chain or not valid_length:
            compiler.error(
                f'{class_name}.{method_name} debe recibir un chain y su Len_t'
            )
        if not (
            return_type.name == 'int32'
            and return_type.pointer_level == 0
            and return_type.array_depth == 0
        ):
            compiler.error(
                f'{class_name}.{method_name} debe retornar int32 (0 o 1)'
            )
        return

    if method_name in _MAGIC_LIFECYCLE_METHODS:
        if parameters:
            compiler.error(
                f'{class_name}.__deletion__ no puede recibir parametros'
            )
        if not (
            return_type.name == 'void'
            and return_type.pointer_level == 0
            and return_type.array_depth == 0
        ):
            compiler.error(f'{class_name}.__deletion__ debe retornar void')
        return

    if method_name in _MAGIC_BINARY_METHODS:
        if len(parameters) != 1 or len(visible) != 1:
            compiler.error(
                f'{class_name}.{method_name} debe recibir exactamente un '
                'parametro explicito'
            )
        if (
            return_type.name in {'void', 'Never'}
            and return_type.pointer_level == 0
            and return_type.array_depth == 0
        ):
            compiler.error(
                f'{class_name}.{method_name} debe retornar un valor'
            )
        return

    if method_name in _MAGIC_UNARY_METHODS:
        if parameters:
            compiler.error(
                f'{class_name}.{method_name} no puede recibir parametros'
            )
        if (
            return_type.name in {'void', 'Never'}
            and return_type.pointer_level == 0
            and return_type.array_depth == 0
        ):
            compiler.error(
                f'{class_name}.{method_name} debe retornar un valor'
            )
        return

    if parameters:
        compiler.error(
            f'{class_name}.__eq__ no puede recibir parametros explicitos'
        )
    if not (
        return_type.name == 'bool'
        and return_type.pointer_level == 0
        and return_type.array_depth == 0
    ):
        compiler.error(f'{class_name}.__eq__ debe retornar bool')


def _parameter_items(parameters: gast.ASTRef) -> list[object]:
    if not parameters.nodes:
        return []
    return _children(parameters.nodes[0])


def _parameter_spec(
    pair: gast.ASTRef,
    *,
    pointer_size: int = 8,
    allow_unique: bool = False,
) -> ParameterSpec:
    declarator = pair.nodes[0]
    type_node = pair.nodes[2]
    name, pointer_level, pointer_is_const = _declarator_info(declarator)
    special_type = _type_name(type_node)
    if special_type in {'Len_t', 'Size_t', 'Region_t'}:
        if special_type == 'Region_t' and not allow_unique:
            raise TypeResolutionError(
                'Region_t solo puede usarse en firmas internas de Bagron'
            )
        if _type_is_unique(type_node):
            raise TypeResolutionError(
                f'{special_type} no puede declararse unique'
            )
        if _type_is_const(type_node):
            raise TypeResolutionError(
                f'{special_type} ya es inmutable; no puede declararse const'
            )
        if pointer_level or len(pair.nodes) > 3:
            raise TypeResolutionError(
                f'{special_type} no puede usar punteros ni valores por defecto'
            )
        return ParameterSpec(
            name=name,
            type_spec=TypeSpec(
                'usize',
                bit_width=pointer_size * 8,
                signed=False,
                value_is_const=True,
            ),
            is_length=special_type == 'Len_t',
            is_size=special_type == 'Size_t',
            is_region=special_type == 'Region_t',
        )
    type_spec = resolve_type(
        type_node,
        pointer_level=pointer_level,
        pointer_is_const=pointer_is_const,
        pointer_size=pointer_size,
        allow_unique=allow_unique,
    )
    is_unique = type_spec.is_unique
    if is_unique:
        if not (type_spec.array_depth or type_spec.name == 'buffer'):
            raise TypeResolutionError(
                f'unique solo puede aplicarse a arrays o buffer; no a {type_spec.canonical_name}'
            )
        type_spec = replace(type_spec, is_unique=False)
    if type_spec.name == 'Never':
        raise TypeResolutionError(
            f'El parametro {name} no puede usar Never'
        )
    if type_spec.name == 'void' and type_spec.pointer_level == 0:
        raise TypeResolutionError(
            f'El parametro {name} no puede usar void por valor'
        )
    return ParameterSpec(
        name=name,
        type_spec=type_spec,
        has_default=len(pair.nodes) > 3,
        is_unique=is_unique,
    )


def _signature_parameters(
    parameters_node: gast.ASTRef,
    *,
    pointer_size: int = 8,
) -> tuple[ParameterSpec, ...]:
    """Resolve visible parameters and named argument-expansion parameters."""
    parameters: list[ParameterSpec] = []
    last_data_parameter: ParameterSpec | None = None
    for item in _parameter_items(parameters_node):
        if not isinstance(item, gast.ASTRef) or item.name != 'PAIR_PARAM':
            continue
        parameter = _parameter_spec(
            item,
            pointer_size=pointer_size,
            allow_unique=True,
        )
        if parameter.is_region:
            if last_data_parameter is None:
                raise TypeResolutionError(
                    'Region_t debe seguir a un parametro unique'
                )
            if not last_data_parameter.is_unique:
                raise TypeResolutionError(
                    f'Region_t solo puede asociarse al parametro unique '
                    f'{last_data_parameter.name}'
                )
            parameters.append(
                ParameterSpec(
                    name=parameter.name,
                    type_spec=parameter.type_spec,
                    has_default=parameter.has_default,
                    is_region=True,
                    region_of=last_data_parameter.name,
                )
            )
            continue
        if parameter.is_length or parameter.is_size:
            if last_data_parameter is None:
                raise TypeResolutionError(
                    'Len_t y Size_t deben seguir a un parametro de datos'
                )
            source_type = last_data_parameter.type_spec
            lengthable_chain = (
                source_type.name == 'chain'
                and source_type.pointer_level == 0
                and source_type.array_depth == 0
            )
            lengthable_array = (
                source_type.pointer_level == 0
                and source_type.array_depth > 0
            )
            if parameter.is_size and is_buffer_type(source_type):
                raise TypeResolutionError(
                    f'Size_t no puede asociarse al buffer {last_data_parameter.name}; '
                    'un buffer siempre tiene elementos de un byte'
                )
            lengthable_buffer = is_buffer_type(source_type)
            if parameter.is_length and not (
                lengthable_chain
                or lengthable_array
                or lengthable_buffer
            ):
                raise TypeResolutionError(
                    'Len_t solo puede asociarse a un parametro array, buffer o chain'
                )
            parameters.append(
                ParameterSpec(
                    name=parameter.name,
                    type_spec=parameter.type_spec,
                    has_default=parameter.has_default,
                    is_length=parameter.is_length,
                    is_size=parameter.is_size,
                    length_of=last_data_parameter.name,
                )
            )
            continue
        parameters.append(parameter)
        last_data_parameter = parameter
    resolved = tuple(parameters)
    _validate_array_expansion_parameters(resolved)
    return resolved


def _validate_array_expansion_parameters(
    parameters: tuple[ParameterSpec, ...],
) -> None:
    """Require the appropriate expansion parameters for data parameters.

    The expansion parameters are compiler-supplied, but they are part of the
    function ABI.  Requiring both values for every array keeps that ABI
    explicit and prevents unsafe functions from silently omitting metadata.
    ``chain`` remains a separate static-string case and only uses ``Len_t``.
    A ``buffer`` carries its byte width in its descriptor, so it only accepts
    ``Len_t``; ``Size_t`` would always be the redundant value ``1``.
    """
    for parameter in parameters:
        type_spec = parameter.type_spec
        if parameter.is_region:
            continue
        if is_buffer_type(type_spec):
            linked = [
                candidate
                for candidate in parameters
                if (
                    (
                        candidate.is_length
                        or candidate.is_size
                        or candidate.is_region
                    )
                    and (
                        candidate.length_of
                        if not candidate.is_region
                        else candidate.region_of
                    ) == parameter.name
                )
            ]
            lengths = [candidate for candidate in linked if candidate.is_length]
            sizes = [candidate for candidate in linked if candidate.is_size]
            regions = [
                (index, candidate)
                for index, candidate in enumerate(parameters)
                if candidate.is_region and candidate.region_of == parameter.name
            ]
            if sizes:
                raise TypeResolutionError(
                    f'El buffer {parameter.name} solo puede declarar Len_t; '
                    'Size_t no aplica a buffers'
                )
            if len(lengths) != 1:
                raise TypeResolutionError(
                    f'El buffer {parameter.name} debe declarar Len_t para '
                    'exponer su longitud en bytes'
                )
            if parameter.is_unique and len(regions) != 1:
                raise TypeResolutionError(
                    f'El buffer unique {parameter.name} debe declarar Region_t'
                )
            if regions and parameters.index(lengths[0]) > regions[0][0]:
                raise TypeResolutionError(
                    f'El buffer {parameter.name} debe declarar Region_t despues de Len_t'
                )
            if not parameter.is_unique and regions:
                raise TypeResolutionError(
                    f'Region_t solo puede asociarse al buffer unique {parameter.name}'
                )
            continue
        if (
            parameter.is_length
            or parameter.is_size
            or type_spec.pointer_level
            or type_spec.array_depth == 0
        ):
            continue

        linked = [
            (index, candidate)
            for index, candidate in enumerate(parameters)
            if (
                (
                    candidate.is_length
                    or candidate.is_size
                    or candidate.is_region
                )
                and (
                    candidate.length_of
                    if not candidate.is_region
                    else candidate.region_of
                ) == parameter.name
            )
        ]
        lengths = [
            (index, candidate)
            for index, candidate in linked
            if candidate.is_length
        ]
        sizes = [
            (index, candidate)
            for index, candidate in linked
            if candidate.is_size
        ]
        regions = [
            (index, candidate)
            for index, candidate in linked
            if candidate.is_region
        ]
        if len(lengths) != 1 or len(sizes) != 1:
            raise TypeResolutionError(
                f'El array {parameter.name} debe declarar Len_t y Size_t; '
                'la longitud y el tamano del elemento son obligatorios'
            )
        if lengths[0][0] > sizes[0][0]:
            raise TypeResolutionError(
                f'El array {parameter.name} debe declarar Len_t antes de Size_t'
            )
        if parameter.is_unique and len(regions) != 1:
            raise TypeResolutionError(
                f'El array unique {parameter.name} debe declarar Region_t'
            )
        if regions and regions[0][0] < sizes[0][0]:
            raise TypeResolutionError(
                f'El array {parameter.name} debe declarar Region_t despues de Size_t'
            )
        if not parameter.is_unique and regions:
            raise TypeResolutionError(
                f'Region_t solo puede asociarse al array unique {parameter.name}'
            )


def signature_from_node(
    node: gast.ASTRef,
    *,
    pointer_size: int = 8,
) -> tuple[str, FunctionSignature]:
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
    parameters = _signature_parameters(parameters_node, pointer_size=pointer_size)

    return_node = children[parameter_index + 1]
    return_pointer = 0
    for child in children[parameter_index + 2:]:
        if isinstance(child, gast.ASTRef) and child.name == 'POINTER':
            return_pointer = len(child.nodes)
            break

    return_type = resolve_type(
        return_node,
        pointer_level=return_pointer,
        pointer_size=pointer_size,
    )
    if return_type.name == 'buffer':
        raise TypeResolutionError(
            f'La funcion {name or "<anonima>"} no puede retornar buffer hasta '
            'definir su ABI de propiedad entre funciones'
        )
    if return_type.name == 'Never' and (
        return_type.pointer_level or return_type.array_depth
    ):
        raise TypeResolutionError(
            'Never solo puede usarse como retorno escalar'
        )
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
        symbol.local_variables[parameter.name] = variable


def collect(compiler: Compiler, nodes: list[gast.ASTRef]) -> None:
    """Register only top-level function signatures and parameter scopes."""
    for node in nodes:
        if node.name != 'FUNCTION':
            continue

        try:
            name, signature = signature_from_node(
                node,
                pointer_size=compiler.storage.pointer_size,
            )
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
        _validate_decorators(compiler, name, decorators)
        symbol = FunctionSymbol(
            name,
            signature,
            decorators=decorators,
            is_inline=_is_inline(node),
            module_path=compiler.module_for_node(node),
            privacy=_privacy(node),
        )
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


def _resolve_function_local(
    symbol: FunctionSymbol,
    scope: Storage | None,
    name: str,
) -> object | None:
    """Resolve only bindings in the function's lexical scope chain.

    A block may assign an outer local, but this helper deliberately stops at
    the function scope so a module global is not mistaken for a local target.
    Normal expression lookup uses the function's explicit global allowlist.
    """
    root = symbol.scope
    current = scope
    while current is not None:
        value = current.namespace.get(name)
        if value is not None:
            return value
        if current is root:
            break
        current = current.parent
    return None


def _validate_return(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: gast.ASTRef,
    scope: Storage | None = None,
) -> None:
    scope = scope or symbol.scope
    if scope is None:
        return

    value_node = _return_value(node)
    return_type = symbol.signature.return_type

    if (
        return_type.name == 'Never'
        and return_type.pointer_level == 0
        and return_type.array_depth == 0
    ):
        compiler.error(
            f'La funcion Never {symbol.name} no puede usar return'
        )
        return

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
            compiler.function_lookup,
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
        symbol.is_method
        and symbol.source_name in _MAGIC_STATUS_METHODS
        and value_info.is_literal
        and value_info.value not in (0, 1)
    ):
        compiler.error(
            f'El metodo magico {symbol.owner_type}.{symbol.source_name} '
            'solo puede retornar 0 o 1'
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


def _for_binding(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: gast.ASTRef,
    scope: Storage | None = None,
) -> str | None:
    scope = scope or symbol.scope
    if scope is None:
        return None

    signature = next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef) and child.name == 'FOR_SIGNATURE'
        ),
        None,
    )
    if signature is None:
        return None

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
        return None

    try:
        type_spec = resolve_type(
            type_node,
            pointer_size=compiler.storage.pointer_size,
        )
    except TypeResolutionError as error:
        compiler.error(f'{name}: {error}')
        return None

    array_value = next(
        (
            child for child in children
            if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
        ),
        None,
    )
    array_form = any(_token_value(child) == 'in' for child in children)

    if array_form:
        if (
            type_spec.name not in INTEGER_TYPES
            or type_spec.pointer_level
            or type_spec.array_depth
        ):
            compiler.error(
                f'El iterador {name} de un array debe tener un tipo entero escalar'
            )
            return None
        if array_value is None:
            compiler.error(f'El for de {name} necesita un array fuente')
            return None
        try:
            array_info = infer_value(
                array_value,
                scope.resolve,
                compiler.function_lookup,
                current_function=symbol,
            )
        except (UnsupportedExpressionError, ValueResolutionError) as error:
            compiler.error(f'El array del for de {name} es invalido: {error}')
            return None
        if (
            not array_info.is_lvalue
            or array_info.type_spec.pointer_level
            or array_info.type_spec.array_depth == 0
        ):
            compiler.error(
                f'El origen de {name} debe ser un array direccionable, no un valor '
                'escalar o un puntero'
            )
            return None
        length = (
            array_info.type_spec.array_lengths[0]
            if array_info.type_spec.array_lengths
            else None
        )
        if length is not None:
            bounds = _integer_bounds(type_spec)
            if bounds is None or length > bounds[1]:
                compiler.error(
                    f'El tamano del array del for de {name} no cabe en '
                    f'{type_spec.canonical_name}'
                )
                return None
            if length > target_iteration_limit(compiler.storage.pointer_size):
                compiler.error(
                    f'El tamano del array del for de {name} excede el limite '
                    'maximo de iteracion del target '
                    f'({target_iteration_limit(compiler.storage.pointer_size)})'
                )
                return None
    elif (
        type_spec.name not in FOR_ITERATOR_TYPES
        or type_spec.pointer_level
        or type_spec.array_depth
    ):
        compiler.error(
            f'El iterador {name} debe tener exactamente un tipo uint8/uint16/uint32/uint64'
        )
        return None

    if not array_form:
        range_values = [
            child for child in children
            if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
        ]
        if len(range_values) != 3:
            compiler.error(f'El rango de {name} debe tener start, end y step')
            return None
        for index, value_node in enumerate(range_values):
            try:
                value_info = infer_value(
                    value_node,
                    scope.resolve,
                    compiler.function_lookup,
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
            if (
                value_info.is_literal
                and isinstance(value_info.value, int)
                and value_info.value > target_iteration_limit(compiler.storage.pointer_size)
            ):
                compiler.error(
                    f'El valor {index + 1} del rango de {name} excede '
                    'el limite maximo de iteracion del target '
                    f'({target_iteration_limit(compiler.storage.pointer_size)})'
                )
            if index == 2 and value_info.is_literal and value_info.value == 0:
                compiler.error(f'El step de {name} no puede ser cero')

    if (
        name in symbol.local_variables
        or name in symbol.global_variables
        or _resolve_function_local(symbol, scope, name) is not None
    ):
        compiler.error(
            f'La variable {name} ya fue declarada en el scope {scope.scope_name}'
        )
        return None

    iterator = build_symbol(scope, name, type_spec, kind='local')
    iterator.is_for_iterator = True
    if array_form and length is not None:
        iterator.for_array_source = array_info.identifier
        iterator.for_array_path = array_info.address_path
        iterator.for_array_length = length
    scope.add(name, iterator)
    symbol.loop_iterators[name] = type_spec
    return name


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


def _deletion_value(node: object) -> object | None:
    return next(
        (
            child for child in _children(node)
            if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
        ),
        None,
    )


def _validate_deletion(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: object,
    scope: Storage | None = None,
) -> None:
    scope = scope or symbol.scope
    if scope is None:
        return

    value_node = _deletion_value(node)
    if value_node is None:
        compiler.error(f'Del en {symbol.name} no contiene una instancia')
        return
    try:
        value_info = infer_value(
            value_node,
            scope.resolve,
            compiler.function_lookup,
            current_function=symbol,
        )
    except (UnsupportedExpressionError, ValueResolutionError) as error:
        compiler.error(f'{symbol.name}: Del es invalido: {error}')
        return

    if is_buffer_type(value_info.type_spec):
        owner = (
            scope.resolve(value_info.identifier)
            if value_info.identifier is not None
            else None
        )
        if owner is not None and getattr(owner, 'scope_kind', None) == 'parameter':
            compiler.error(
                f'Del en {symbol.name} no puede liberar un buffer recibido como '
                'parametro; la propiedad entre funciones aun no esta definida'
            )
            return
        if not value_info.is_lvalue:
            compiler.error(
                f'Del en {symbol.name} requiere una variable propietaria de buffer'
            )
        return

    aggregate = compiler.storage.resolve_type(value_info.type_spec.name)
    if not (
        isinstance(aggregate, AggregateSymbol)
        and aggregate.is_class
        and value_info.type_spec.pointer_level == 0
        and value_info.type_spec.array_depth == 0
    ):
        compiler.error(
            f'Del en {symbol.name} requiere una instancia escalar de class'
        )


def _validate_condition(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: object,
    scope: Storage | None = None,
) -> None:
    scope = scope or symbol.scope
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
            compiler.function_lookup,
            current_function=symbol,
        )
    except (UnsupportedExpressionError, ValueResolutionError) as error:
        compiler.error(f'La condicion de {symbol.name} es invalida: {error}')
        return

    aggregate = compiler.storage.resolve_type(value_info.type_spec.name)
    is_class_instance = bool(
        isinstance(aggregate, AggregateSymbol)
        and aggregate.is_class
        and value_info.type_spec.pointer_level == 0
        and value_info.type_spec.array_depth == 0
    )

    condition_kind = {
        'IF_SIGNATURE': 'if',
        'ELIF_SIGNATURE': 'elif',
        'WHILE_SIGNATURE': 'while',
    }.get(node.name)
    if condition_kind is not None:
        if not is_bool_scalar(value_info.type_spec) and not is_class_instance:
            compiler.error(
                f'La condicion de {condition_kind} en {symbol.name} debe ser '
                'bool o una instancia de class'
            )
        return

    if not is_condition_type(value_info.type_spec) and not is_class_instance:
        compiler.error(
            f'La condicion de {symbol.name} debe ser bool o una instancia de '
            'class'
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


def _validate_char_array_write(
    compiler: Compiler,
    symbol: FunctionSymbol,
    target_info,
    variable,
    name: str | None,
) -> bool:
    """Protect the hidden terminator without emitting runtime checks."""
    if symbol.is_unsafe or variable is None:
        return True

    type_spec = getattr(variable, 'type_spec', None)
    if (
        type_spec is None
        or type_spec.name != 'char'
        or type_spec.array_depth != 1
    ):
        return True

    length = type_spec.array_lengths[0] if type_spec.array_lengths else None
    if length is None:
        return True

    indexes = [
        entry[1]
        for entry in target_info.address_path
        if isinstance(entry, tuple) and entry and entry[0] == 'index'
    ]
    if not indexes:
        return True

    index = indexes[-1]
    if index.is_literal and index.value == length - 1:
        compiler.error(
            f'La escritura de {name or "<anonimo>"} no puede modificar '
            'el terminador NUL reservado'
        )
        return False
    return True


def _validate_assignment(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: gast.ASTRef,
    scope: Storage | None = None,
) -> None:
    scope = scope or symbol.scope
    if scope is None:
        return

    target, operator, value_node = _assignment_parts(node)
    name = _identifier(target) if target is not None else None
    variable = _resolve_function_local(symbol, scope, name or '')
    global_variable = (
        _module_variable(compiler, name or '')
        if name in symbol.global_variables
        else None
    )
    binding = variable if variable is not None else global_variable
    try:
        target_info = infer_lvalue(
            target,
            scope.resolve,
            compiler.function_lookup,
            current_function=symbol,
        )
    except (UnsupportedExpressionError, ValueResolutionError) as error:
        compiler.error(f'{symbol.name}: {error}')
        return

    member_owner = getattr(target_info, 'member_owner', None)
    frozen_owner = (
        compiler.storage.resolve_type(member_owner)
        if member_owner
        else None
    )
    if (
        isinstance(frozen_owner, AggregateSymbol)
        and frozen_owner.is_class
        and frozen_owner.is_frozen
    ):
        compiler.error(
            f'La clase @frozen {frozen_owner.name} no permite modificar sus '
            'atributos despues de inicializarse'
        )
        return

    if binding is None and target_info.storage_origin != 'local':
        compiler.error(
            f'La asignacion de {symbol.name} requiere una variable local: '
            f'{name or "<anonima>"}'
        )
        return
    if (
        binding is not None
        and getattr(binding, 'is_receiver', False)
        and not target_info.address_path
    ):
        compiler.error(
            f'El receptor self del metodo {symbol.name} no puede reasignarse'
        )
        return
    if binding is not None and (
        binding.value_is_const
        or (
            binding.type_spec.pointer_level > 0
            and binding.pointer_is_const
        )
    ):
        compiler.error(f'La variable constante no puede asignarse: {name}')
        return
    if binding is not None and getattr(binding, 'is_for_iterator', False):
        compiler.error(f'El iterador {name} es de solo lectura dentro del for')
        return
    if target_info.type_spec.value_is_const:
        compiler.error(
            f'El valor apuntado por {name or "<anonimo>"} no puede asignarse'
        )
        return
    if not _validate_char_array_write(
        compiler,
        symbol,
        target_info,
        binding,
        name,
    ):
        return
    if operator is None or value_node is None:
        compiler.error(f'La asignacion de {symbol.name} es invalida')
        return

    try:
        value_info = infer_value(
            value_node,
            scope.resolve,
            compiler.function_lookup,
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

    if is_buffer_type(target_info.type_spec) or is_buffer_type(value_info.type_spec):
        compiler.error(
            f'La asignacion de {name} no puede copiar buffers; la transferencia '
            'de propiedad aun no esta definida'
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
        binding is not None
        and operator == '='
        and target_info.type_spec.pointer_level > 0
    ):
        # Pointer provenance is flow-sensitive at the declaration/assignment
        # level.  Unknown values remain unknown in safe functions and are
        # rejected only when a later operation dereferences them.
        binding.value_info = value_info


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
    symbol.has_asm_body = bool(prep_count)
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
        is_void = (
            symbol.signature.return_type.name == 'void'
            and symbol.signature.return_type.pointer_level == 0
            and symbol.signature.return_type.array_depth == 0
        )
        if not is_void and return_asm_count != 1:
            compiler.error(
                f'La funcion @assembler {symbol.name} requiere un unico return asm'
            )
        if is_void and return_asm_count:
            compiler.error(
                f'La funcion void @assembler {symbol.name} no puede usar return asm'
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

    if symbol.signature.return_type.name not in INTEGER_TYPES or (
        symbol.signature.return_type.pointer_level
        or symbol.signature.return_type.array_depth
    ):
        compiler.error(
            f'La funcion @assembler {symbol.name} debe retornar un entero '
            'escalar'
        )
        return

    symbol.return_asm_node = node


def _statement_body_guarantees_return(
    body: object,
    symbol: FunctionSymbol | None = None,
) -> bool:
    return _statement_sequence_guarantees_return(_children(body), symbol)


def _statement_sequence_guarantees_return(
    nodes: list[object],
    symbol: FunctionSymbol | None = None,
) -> bool:
    """Return whether one sequential path must terminate.

    A source ``return`` and a standalone call to a ``Never`` function both
    terminate the current path.

    Loops are deliberately not considered guaranteed returns: a ``while`` may
    execute zero times and a ``for`` may have an empty range.  This keeps a
    terminating statement nested only inside a loop from masking a missing
    fall-through path.
    """
    for node in nodes:
        if isinstance(node, list):
            if _statement_sequence_guarantees_return(node, symbol):
                return True
            continue
        if _statement_guarantees_return(node, symbol):
            return True
    return False


def _if_guarantees_return(
    node: gast.ASTRef,
    symbol: FunctionSymbol | None = None,
) -> bool:
    branches: list[object] = []
    else_body = None
    awaiting_if_body = False

    for child in _children(node):
        name = getattr(child, 'name', None)
        if name == 'IF_SIGNATURE':
            awaiting_if_body = True
        elif name == 'STATEMENT_BODY' and awaiting_if_body:
            branches.append(child)
            awaiting_if_body = False
        elif name in {'ELIF', 'ELSE'}:
            body = next(
                (
                    item for item in _children(child)
                    if getattr(item, 'name', None) == 'STATEMENT_BODY'
                ),
                None,
            )
            if name == 'ELIF':
                if body is None:
                    return False
                branches.append(body)
            else:
                else_body = body

    if else_body is None or not branches:
        return False
    return all(
        _statement_body_guarantees_return(branch, symbol)
        for branch in (*branches, else_body)
    )


def _statement_guarantees_return(
    node: object,
    symbol: FunctionSymbol | None = None,
) -> bool:
    if not isinstance(node, gast.ASTRef):
        return False
    if node.name in {'RETURN', 'RETURN_ASM'}:
        return True
    if (
        node.name == 'CALL'
        and symbol is not None
        and id(node) in symbol.never_call_nodes
    ):
        return True
    if node.name in {'FUNCTION_BODY', 'STATEMENT_BODY'}:
        return _statement_body_guarantees_return(node, symbol)
    if node.name == 'IF':
        return _if_guarantees_return(node, symbol)
    return False


def _new_block_scope(parent: Storage, symbol: FunctionSymbol) -> Storage:
    """Create a lexical block scope without changing runtime storage rules."""
    root = symbol.scope.root if symbol.scope is not None else parent.root
    return Storage(
        root,
        parent=parent,
        scope_name=f'{parent.scope_name}:block',
    )


def _process_body_node(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: object,
    returns: list[int],
    scope: Storage | None = None,
    loop_depth: int = 0,
) -> None:
    scope = scope or symbol.scope
    if scope is None:
        return

    if isinstance(node, gast.ASTKeyword):
        if _token_value(node) in {'break', 'continue'} and loop_depth == 0:
            compiler.error(
                f'{_token_value(node)} solo puede usarse dentro de un bucle'
            )
        return
    if isinstance(node, list):
        for child in node:
            _process_body_node(
                compiler,
                symbol,
                child,
                returns,
                scope,
                loop_depth,
            )
        return
    if not isinstance(node, gast.ASTRef):
        return

    if node.name == 'STATEMENT_BODY':
        block_scope = _new_block_scope(scope, symbol)
        for child in _children(node):
            _process_body_node(
                compiler,
                symbol,
                child,
                returns,
                block_scope,
                loop_depth,
            )
        return

    if node.name in _DEFINITION_NODES:
        return
    if node.name == 'GLOBAL':
        return
    if node.name == 'VAR':
        handle = handle_variable(node)
        if handle is None:
            return
        if handle.name in symbol.global_variables:
            compiler.error(
                f'La variable {handle.name} fue declarada como global y no '
                f'puede redeclararse como local en {symbol.name}'
            )
            return
        if handle.name in symbol.local_variables:
            compiler.error(
                f'La variable {handle.name} ya fue declarada en la funcion '
                f'{symbol.name}; no se permite shadowing ni reutilizacion'
            )
            return
        variable = collect_local(
            compiler,
            scope,
            node,
            current_function=symbol,
        )
        if variable is not None:
            symbol.local_variables[handle.name] = variable
        return
    if node.name == 'VAR_ASSIGNATION':
        _validate_assignment(compiler, symbol, node, scope)
        return
    if node.name == 'DEL':
        _validate_deletion(compiler, symbol, node, scope)
        symbol.body_supported_for_entrypoint = False
        return
    if node.name == 'RETURN':
        _validate_return(compiler, symbol, node, scope)
        returns[0] += 1
        return
    if node.name == 'RETURN_ASM':
        _validate_return_asm(compiler, symbol, node)
        returns[0] += 1
        return
    loop_name = None
    if node.name == 'FOR':
        loop_name = _for_binding(compiler, symbol, node, scope)

    if node.name == 'CALL':
        try:
            call_info = infer_call(
                node,
                scope.resolve,
                compiler.function_lookup,
                current_function=symbol,
            )
            if (
                call_info.type_spec.name == 'Never'
                and call_info.type_spec.pointer_level == 0
                and call_info.type_spec.array_depth == 0
            ):
                symbol.never_call_nodes.add(id(node))
        except (UnsupportedExpressionError, ValueResolutionError) as error:
            compiler.error(f'{symbol.name}: {error}')

    if node.name in {'IF_SIGNATURE', 'ELIF_SIGNATURE', 'WHILE_SIGNATURE'}:
        _validate_condition(compiler, symbol, node, scope)

    if node.name in {'CALL', 'IF', 'WHILE'}:
        symbol.body_supported_for_entrypoint = False

    child_loop_depth = loop_depth + (node.name in {'FOR', 'WHILE'})
    for child in _children(node):
        _process_body_node(
            compiler,
            symbol,
            child,
            returns,
            scope,
            child_loop_depth,
        )

    if node.name == 'FOR' and loop_name is not None:
        iterator = scope.namespace.get(loop_name)
        if getattr(iterator, 'is_for_iterator', False):
            # The iterator is visible only while this FOR body is being
            # checked. Backend emission keeps its own hidden storage.
            del scope.namespace[loop_name]


def process(compiler: Compiler, node: gast.ASTRef) -> None:
    """Collect local variables and validate returns for one top-level function."""
    symbol = compiler.function_bindings.get(id(node))
    if symbol is None:
        return

    compiler.activate_module(symbol.module_path)

    body = _body_node(node)
    if body is None:
        compiler.error(f'La funcion {symbol.name} no tiene cuerpo')
        return

    symbol.body_node = body

    _register_global_declarations(compiler, symbol, body)

    _validate_assembler_body(compiler, symbol, body)

    returns = [0]
    if symbol.scope is not None:
        for child in _children(body):
            _process_body_node(compiler, symbol, child, returns, symbol.scope)

    return_type = symbol.signature.return_type
    body_terminates = _statement_body_guarantees_return(body, symbol)
    if (
        symbol.has_asm_body
        and return_type.name == 'void'
        and return_type.pointer_level == 0
        and return_type.array_depth == 0
    ):
        body_terminates = True
    symbol.body_terminates = body_terminates or (
        return_type.name == 'Never'
        and return_type.pointer_level == 0
        and return_type.array_depth == 0
    )
    if not body_terminates and not symbol.body_terminates:
        if return_type.name == 'void' and return_type.pointer_level == 0:
            compiler.error(
                f'La funcion void {symbol.name} debe terminar con return'
            )
        elif not (
            return_type.name == 'void'
            and return_type.pointer_level == 0
        ):
            compiler.error(f'La funcion {symbol.name} no tiene return')


__all__ = [
    'collect',
    'process',
    'signature_from_node',
    'validate_magic_method_signature',
]

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from core.frontend.objects import (
    AggregateSymbol,
    FunctionSignature,
    FunctionSymbol,
    ParameterSpec,
    TypeSpec,
    ValueInfo,
)
from core.frontend.tools.types import (
    FLOAT_TYPES,
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
    _integer_width,
    _type_is_const,
    _type_is_unique,
    _type_name,
)
from core.frontend.tools.variable import build_symbol, collect_local
from core.frontend.tools.opaque import is_opaque_type, validate_opaque_use
from core.frontend.tools.ranges import (
    body_preserves_range,
    fact_from_condition,
    for_fact,
)
from core.frontend.handles.variables import handle_variable
from core.frontend.ownership import (
    BORROWED,
    DEAD,
    OWNED,
    analyze_if,
    analyze_loop,
    is_buffer_symbol,
    set_state as set_buffer_state,
    state_for as buffer_state_for,
)
from gram import ast as gast

from core.storage import Storage

if TYPE_CHECKING:
    from core.compiler import Compiler


_FUNCTION_DECORATORS = frozenset({'unsafe', 'assembler', 'recursive'})
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


def _module_variable(compiler: Compiler, name: str) -> object | None:
    return compiler.storage.resolve_module_value(name)


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


def _unwrap_call_expression(node: object) -> object:
    current = node
    while (
        isinstance(current, gast.ASTRef)
        and current.name in {'VALUE', 'POSTFIX_EXPR', 'PRIMARY'}
        and len(_children(current)) == 1
    ):
        current = _children(current)[0]
    return current


def _call_name_from_node(node: object) -> str | None:
    current = _unwrap_call_expression(node)
    if not isinstance(current, gast.ASTRef) or current.name not in {
        'CALL', 'POSTFIX_EXPR'
    }:
        return None
    children = _children(current)
    primary = children[0] if children else None
    suffixes: list[object] = []
    for child in children[1:]:
        suffixes.extend(_children(child) if isinstance(child, list) else [child])
    if not any(
        getattr(suffix, 'name', None) == 'CALL_SUFFIX'
        for suffix in suffixes
    ):
        return None
    name = _identifier(primary)
    for suffix in suffixes:
        if getattr(suffix, 'name', None) != 'MEMBER_ACCESS':
            continue
        member = _identifier(suffix)
        if member is not None:
            name = f'{name}.{member}' if name else member
    return name


def _contains_descendant_call(node: object, function_name: str) -> bool:
    return any(
        _call_name_from_node(child) == function_name
        or _contains_descendant_call(child, function_name)
        for child in _children(node)
    )


def _tail_recursive_candidate(symbol: FunctionSymbol) -> bool:
    """Accept only direct tail calls that can reuse one simple frame."""
    if symbol.name == 'main' or symbol.is_method or symbol.is_external:
        return False
    if any(
        parameter.is_length
        or parameter.is_size
        or parameter.is_signed
        or parameter.is_region
        or parameter.type_spec.name == 'chain'
        for parameter in symbol.signature.parameters
    ):
        return False
    if any(
        getattr(variable, 'scope_kind', None) != 'parameter'
        for variable in getattr(symbol, 'local_variables', {}).values()
    ):
        return False

    found = False
    invalid = False

    def visit(node: object) -> None:
        nonlocal found, invalid
        if not isinstance(node, gast.ASTRef):
            for child in _children(node):
                visit(child)
            return
        if node.name == 'RETURN':
            value = _return_value(node)
            if value is None:
                return
            if _call_name_from_node(value) == symbol.name:
                if _contains_descendant_call(
                    _unwrap_call_expression(value),
                    symbol.name,
                ):
                    invalid = True
                else:
                    found = True
            elif _contains_descendant_call(value, symbol.name):
                invalid = True
            return
        if _call_name_from_node(node) == symbol.name:
            invalid = True
        for child in _children(node):
            visit(child)

    if symbol.body_node is None:
        return False
    visit(symbol.body_node)
    return found and not invalid


def _recursive_components(
    symbols: list[FunctionSymbol],
) -> list[list[FunctionSymbol]]:
    by_id = {id(symbol): symbol for symbol in symbols}
    graph = {
        id(symbol): [
            id(target)
            for target in getattr(symbol, 'called_functions', ())
            if id(target) in by_id
        ]
        for symbol in symbols
    }
    index = 0
    indices: dict[int, int] = {}
    lowlinks: dict[int, int] = {}
    stack: list[int] = []
    on_stack: set[int] = set()
    components: list[list[FunctionSymbol]] = []

    def visit(node_id: int) -> None:
        nonlocal index
        indices[node_id] = index
        lowlinks[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)

        for target_id in graph[node_id]:
            if target_id not in indices:
                visit(target_id)
                lowlinks[node_id] = min(lowlinks[node_id], lowlinks[target_id])
            elif target_id in on_stack:
                lowlinks[node_id] = min(lowlinks[node_id], indices[target_id])

        if lowlinks[node_id] != indices[node_id]:
            return
        component_ids: list[int] = []
        while True:
            target_id = stack.pop()
            on_stack.remove(target_id)
            component_ids.append(target_id)
            if target_id == node_id:
                break
        components.append([by_id[item] for item in component_ids])

    for symbol in symbols:
        if id(symbol) not in indices:
            visit(id(symbol))
    return components


def validate_recursion(compiler: Compiler) -> None:
    """Reject unmarked recursive cycles after all calls have been resolved."""
    symbols: list[FunctionSymbol] = []
    seen: set[int] = set()
    for symbol in [
        *compiler.storage.functions.values(),
        *compiler.storage.methods.values(),
    ]:
        if id(symbol) not in seen and not symbol.is_external:
            seen.add(id(symbol))
            symbols.append(symbol)

    for symbol in symbols:
        if any(target is symbol for target in symbol.called_functions):
            symbol.tail_recursive = _tail_recursive_candidate(symbol)

    for component in _recursive_components(symbols):
        is_self_cycle = len(component) == 1 and any(
            target is component[0]
            for target in component[0].called_functions
        )
        if len(component) == 1 and not is_self_cycle:
            continue
        if is_self_cycle and component[0].tail_recursive:
            continue
        missing = [symbol for symbol in component if not symbol.is_recursive]
        if not missing:
            continue
        cycle = ' -> '.join(sorted(symbol.name for symbol in component))
        for symbol in missing:
            compiler.error(
                f'La funcion {symbol.name} participa en una recursividad sin '
                f'limite declarado (ciclo: {cycle}); usa @recursive'
            )


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
            or parameter.is_signed
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
    if special_type in {'Len_t', 'Size_t', 'Signed_t', 'Region_t'}:
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
            is_signed=special_type == 'Signed_t',
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
        if parameter.is_length or parameter.is_size or parameter.is_signed:
            if last_data_parameter is None:
                raise TypeResolutionError(
                    'Len_t, Size_t y Signed_t deben seguir a un parametro de datos'
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
                    is_signed=parameter.is_signed,
                    length_of=last_data_parameter.name,
                    signed_of=(
                        last_data_parameter.name if parameter.is_signed else None
                    ),
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
    ``Len_t``; ``Size_t`` would always be the redundant value ``1``. ``Signed_t``
    is optional and follows the other array metadata when requested.
    """
    def source_name(candidate: ParameterSpec) -> str | None:
        if candidate.is_region:
            return candidate.region_of
        if candidate.is_signed:
            return candidate.signed_of
        return candidate.length_of

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
                        or candidate.is_signed
                        or candidate.is_region
                    )
                    and source_name(candidate) == parameter.name
                )
            ]
            lengths = [candidate for candidate in linked if candidate.is_length]
            sizes = [candidate for candidate in linked if candidate.is_size]
            signed = [candidate for candidate in linked if candidate.is_signed]
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
            if len(signed) > 1:
                raise TypeResolutionError(
                    f'El buffer {parameter.name} no puede declarar Signed_t mas de una vez'
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
            if signed and parameters.index(signed[0]) < parameters.index(lengths[0]):
                raise TypeResolutionError(
                    f'El buffer {parameter.name} debe declarar Signed_t despues de Len_t'
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
            or parameter.is_signed
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
                    or candidate.is_signed
                    or candidate.is_region
                )
                and source_name(candidate) == parameter.name
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
        signed = [
            (index, candidate)
            for index, candidate in linked
            if candidate.is_signed
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
        if len(signed) > 1:
            raise TypeResolutionError(
                f'El array {parameter.name} no puede declarar Signed_t mas de una vez'
            )
        if lengths[0][0] > sizes[0][0]:
            raise TypeResolutionError(
                f'El array {parameter.name} debe declarar Len_t antes de Size_t'
            )
        if signed and signed[0][0] < sizes[0][0]:
            raise TypeResolutionError(
                f'El array {parameter.name} debe declarar Signed_t despues de Size_t'
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


_PURE_RETURN_TYPES = INTEGER_TYPES | {
    'bool',
    'char',
    'chain',
    'middle',
    'float',
    'double',
}


def _validate_return_type(
    compiler: Compiler,
    name: str,
    return_type: TypeSpec,
) -> None:
    """Keep source-level returns value-like and free of borrowed storage.

    Arrays, buffers and pointers are represented by storage or addresses whose
    lifetime belongs to a caller or scope. Bagron functions do not transfer
    those resources through returns; aggregates remain valid value results.
    ``extern`` declarations use their separate ABI validator.
    """
    if return_type.name == 'buffer':
        raise TypeResolutionError(
            f'La funcion {name or "<anonima>"} no puede retornar buffer; '
            'los buffers solo se rellenan mediante parametros'
        )
    if return_type.pointer_level:
        raise TypeResolutionError(
            f'La funcion {name or "<anonima>"} no puede retornar punteros; '
            'solo puede retornar valores intrinsecos u objetos'
        )
    if return_type.array_depth:
        raise TypeResolutionError(
            f'La funcion {name or "<anonima>"} no puede retornar arrays; '
            'solo puede retornar valores intrinsecos u objetos'
        )
    validate_opaque_use(
        compiler.storage,
        return_type,
        f'El retorno de {name or "<anonima>"}',
    )
    if is_opaque_type(compiler.storage, return_type):
        return
    if (
        return_type.name in {'void', 'Never'}
        or return_type.name in _PURE_RETURN_TYPES
    ):
        return
    if compiler.storage.resolve_type(return_type.name) is not None:
        return
    raise TypeResolutionError(
        f'El retorno de {name or "<anonima>"} debe ser un intrinseco puro '
        'o un objeto agregado (struct, mold, flags o class)'
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

        compiler.activate_module(compiler.module_for_node(node))
        try:
            name, signature = signature_from_node(
                node,
                pointer_size=compiler.storage.pointer_size,
            )
            _validate_return_type(compiler, name, signature.return_type)
            for parameter in signature.parameters:
                validate_opaque_use(
                    compiler.storage,
                    parameter.type_spec,
                    f'El parametro {parameter.name} de {name or "<anonima>"}',
                )
        except TypeResolutionError as error:
            compiler.error(str(error))
            continue

        if not name:
            compiler.error('La funcion no tiene nombre')
            continue
        if any(
            getattr(existing, 'module_path', None) == compiler.module_for_node(node)
            for existing in compiler.storage.function_candidates.get(name, ())
        ):
            compiler.error(f'La funcion ya fue declarada: {name}')
            continue

        decorators = _decorator_names(node)
        _validate_decorators(compiler, name, decorators)
        symbol = FunctionSymbol(
            name,
            signature,
            source_name=name,
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
    """Resolve bindings in the function's lexical scope chain only.

    A block may assign an outer local; module values are resolved by Storage.
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
        or _resolve_function_local(symbol, scope, name) is not None
    ):
        compiler.error(
            f'La variable {name} ya fue declarada en el scope {scope.scope_name}'
        )
        return None

    iterator = build_symbol(scope, name, type_spec, kind='local')
    iterator.is_for_iterator = True
    if array_form:
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


def _validate_buffer_deletion(
    compiler: Compiler,
    symbol: FunctionSymbol,
    value_info: ValueInfo,
    scope: Storage,
    loop_depth: int,
) -> None:
    """Apply the ``owned -> dead`` transition for one buffer binding.

    The caller has already resolved the expression as a buffer.  Keeping this
    policy separate makes ``_validate_deletion`` readable: class destruction
    and buffer ownership follow different rules.
    """
    owner = (
        scope.resolve(value_info.identifier)
        if value_info.identifier is not None
        else None
    )
    owner_state = buffer_state_for(symbol, owner)
    display_name = value_info.identifier or '<anonimo>'
    if owner_state == BORROWED:
        compiler.error(
            f'Del en {symbol.name} no puede liberar un buffer '
            f'{display_name}: su estado es borrowed'
        )
        return
    if not value_info.is_lvalue:
        compiler.error(
            f'Del en {symbol.name} requiere una variable propietaria de buffer'
        )
        return
    if owner_state != OWNED:
        compiler.error(
            f'Del en {symbol.name} requiere un buffer owned; '
            f'{display_name} esta en estado {owner_state or "desconocido"}'
        )
        return
    if loop_depth > 0:
        compiler.error(
            f'Del en {symbol.name} no puede liberar el buffer {display_name} '
            'dentro de un bucle: una segunda iteracion lo dejaria en estado dead'
        )
        return
    set_buffer_state(symbol, owner, DEAD)


def _validate_deletion(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: object,
    scope: Storage | None = None,
    loop_depth: int = 0,
) -> None:
    scope = scope or symbol.scope
    if scope is None:
        return

    value_node = _deletion_value(node)
    if value_node is None:
        compiler.error(f'Del en {symbol.name} no contiene una instancia')
        return

    # Check the root binding before normal value inference so a second Del
    # receives a precise diagnostic instead of the generic use-after-Del one.
    deletion_name = _identifier(value_node)
    deletion_symbol = (
        scope.resolve(deletion_name)
        if deletion_name is not None
        else None
    )
    if is_buffer_symbol(deletion_symbol) and (
        buffer_state_for(symbol, deletion_symbol) == DEAD
    ):
        compiler.error(
            f'Del en {symbol.name} no puede liberar el buffer {deletion_name}: '
            'su estado ya es dead'
        )
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
        _validate_buffer_deletion(
            compiler, symbol, value_info, scope, loop_depth
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
    binding = variable
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

    if binding is None:
        global_variable = _module_variable(
            compiler,
            getattr(target_info, 'identifier', None) or name or '',
        )
        binding = global_variable

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

    if operator != '=':
        valid_types = (
            INTEGER_TYPES | FLOAT_TYPES
            if operator in ('+=', '-=', '*=', '/=')
            else INTEGER_TYPES
        )
        if (
            target_info.type_spec.name not in valid_types
            or target_info.type_spec.pointer_level
            or target_info.type_spec.array_depth
        ):
            expected = 'enteros o flotantes' if operator in ('+=', '-=', '*=', '/=') else 'enteros'
            compiler.error(
                f'La asignacion {operator} solo admite {expected} escalares: {name}'
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

    # A raw helper whose complete body is ``mov rax, {parameter}`` is a
    # checked integer narrowing primitive. Preserve its native definition
    # for external callers, but let LLVM replace internal calls with a real
    # truncation so the helper does not cost another call.
    blocks = [
        block for block in getattr(compiler, 'prep_blocks', ())
        if block.function_name == symbol.name
    ]
    if len(blocks) != 1 or len(symbol.signature.parameters) != 1:
        return
    instruction_lines = [
        line.strip()
        for line in blocks[0].body.splitlines()
        if line.strip() and not line.strip().startswith((';', '#'))
    ]
    if len(instruction_lines) != 1:
        return
    instruction = instruction_lines[0]
    mnemonic, separator, operands = instruction.partition(' ')
    if not separator or mnemonic.lower() != 'mov':
        return
    destination, separator, source = operands.partition(',')
    if (
        not separator
        or destination.strip().lower() != 'rax'
        or not source.strip().startswith('{')
        or not source.strip().endswith('}')
    ):
        return
    source_name = source.strip()[1:-1].strip()
    parameter = symbol.signature.parameters[0]
    if source_name != parameter.name:
        return
    source_width = _integer_width(parameter.type_spec)
    return_width = _integer_width(symbol.signature.return_type)
    if (
        source_width is None
        or return_width is None
        or source_width <= return_width
        or parameter.type_spec.pointer_level
        or parameter.type_spec.array_depth
        or symbol.signature.return_type.pointer_level
        or symbol.signature.return_type.array_depth
    ):
        return
    symbol.assembler_intrinsic = 'truncate'


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


def _process_if_node(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: gast.ASTRef,
    returns: list[int],
    scope: Storage,
    loop_depth: int,
) -> None:
    pending_fact: list[object | None] = []

    def visit(child: object) -> None:
        if (
            isinstance(child, gast.ASTRef)
            and child.name in {'IF_SIGNATURE', 'ELIF_SIGNATURE'}
        ):
            _process_body_node(
                compiler, symbol, child, returns, scope, loop_depth
            )
            fact = fact_from_condition(symbol, _condition_value(child))
            pending_fact.append(fact)
            return
        if (
            isinstance(child, gast.ASTRef)
            and child.name == 'STATEMENT_BODY'
            and pending_fact
        ):
            fact = pending_fact.pop()
            if fact is not None and not body_preserves_range(child, fact):
                fact = None
            if fact is not None:
                symbol.range_facts.append(fact)
            try:
                _process_body_node(
                    compiler, symbol, child, returns, scope, loop_depth
                )
            finally:
                if fact is not None:
                    symbol.range_facts.pop()
            return
        _process_body_node(
            compiler, symbol, child, returns, scope, loop_depth
        )

    if analyze_if(symbol, node, symbol.local_variables, visit):
        symbol.body_supported_for_entrypoint = False


def _process_loop_node(
    compiler: Compiler,
    symbol: FunctionSymbol,
    node: gast.ASTRef,
    returns: list[int],
    scope: Storage,
    loop_depth: int,
) -> None:
    loop_name = None
    range_fact = None
    if node.name == 'FOR':
        loop_name = _for_binding(compiler, symbol, node, scope)
        if loop_name is not None:
            range_fact = for_fact(scope.namespace.get(loop_name))
    else:
        signature = next(
            (
                child for child in _children(node)
                if isinstance(child, gast.ASTRef)
                and child.name == 'WHILE_SIGNATURE'
            ),
            None,
        )
        range_fact = fact_from_condition(
            symbol,
            _condition_value(signature) if signature is not None else None,
        )
        body = next(
            (
                child for child in _children(node)
                if isinstance(child, gast.ASTRef)
                and child.name == 'STATEMENT_BODY'
            ),
            None,
        )
        if range_fact is not None and body is not None and not body_preserves_range(
            body, range_fact
        ):
            range_fact = None

    def visit(child: object) -> None:
        _process_body_node(
            compiler,
            symbol,
            child,
            returns,
            scope,
            loop_depth + 1,
        )

    if range_fact is not None:
        symbol.range_facts.append(range_fact)
    try:
        analyze_loop(symbol, _children(node), symbol.local_variables, visit)
    finally:
        if range_fact is not None:
            symbol.range_facts.pop()
    symbol.body_supported_for_entrypoint = False

    if node.name == 'FOR' and loop_name is not None:
        iterator = scope.namespace.get(loop_name)
        if getattr(iterator, 'is_for_iterator', False):
            del scope.namespace[loop_name]


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
    if node.name == 'VAR':
        handle = handle_variable(node)
        if handle is None:
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
        _validate_deletion(compiler, symbol, node, scope, loop_depth)
        symbol.body_supported_for_entrypoint = False
        return
    if node.name == 'IF':
        _process_if_node(
            compiler, symbol, node, returns, scope, loop_depth
        )
        return
    if node.name in {'FOR', 'WHILE'}:
        _process_loop_node(
            compiler, symbol, node, returns, scope, loop_depth
        )
        return
    if node.name == 'RETURN':
        _validate_return(compiler, symbol, node, scope)
        returns[0] += 1
        return
    if node.name == 'RETURN_ASM':
        _validate_return_asm(compiler, symbol, node)
        returns[0] += 1
        return
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

    for child in _children(node):
        _process_body_node(
            compiler,
            symbol,
            child,
            returns,
            scope,
            loop_depth,
        )


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
    symbol.buffer_states.clear()
    symbol.range_facts.clear()

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
    'validate_recursion',
    'signature_from_node',
    'validate_magic_method_signature',
]

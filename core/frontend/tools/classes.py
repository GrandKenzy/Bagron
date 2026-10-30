from __future__ import annotations

from typing import TYPE_CHECKING

from core.frontend.objects import (
    AggregateSymbol,
    FieldSpec,
    FunctionSignature,
    FunctionSymbol,
    ParameterSpec,
    TypeSpec,
)
from core.frontend.tools.types import (
    TypeResolutionError,
    UnsupportedExpressionError,
    ValueResolutionError,
    infer_value,
    is_compatible,
)
from core.frontend.tools.variable import build_symbol
from core.storage import Storage
from gram import ast as gast

if TYPE_CHECKING:
    from core.compiler import Compiler


_INITIALIZER_NAMES = frozenset({'__init__', '__frontend__'})
_CLASS_DECORATORS = frozenset({'frozen'})


def _children(node: object) -> list[object]:
    if isinstance(node, list):
        return list(node)
    nodes = getattr(node, 'nodes', None)
    if nodes is not None:
        return list(nodes)
    items = getattr(node, 'items', None)
    if items is not None:
        return list(items)
    return []


def _token_kind(node: object) -> str | None:
    token = getattr(node, 'token', None)
    token = getattr(token, 'token', token)
    return getattr(token, 'name', None)


def _token_value(node: object) -> object | None:
    token = getattr(node, 'token', None)
    return getattr(token, 'value', None)


def _identifier(node: object) -> str | None:
    if _token_kind(node) == 'IDENT':
        return str(_token_value(node))
    for child in _children(node):
        found = _identifier(child)
        if found is not None:
            return found
    return None


def _identifiers(node: object) -> list[str]:
    if _token_kind(node) == 'IDENT':
        return [str(_token_value(node))]
    result: list[str] = []
    for child in _children(node):
        result.extend(_identifiers(child))
    return result


def _class_parent_names(node: gast.ASTRef) -> list[str]:
    signature = next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef) and child.name == 'CLASS_SIGNATURE'
        ),
        None,
    )
    hierarchy = next(
        (
            child for child in _children(signature)
            if isinstance(child, gast.ASTRef) and child.name == 'CLASS_HERENCY'
        ),
        None,
    ) if signature is not None else None
    return _identifiers(hierarchy) if hierarchy is not None else []


def _call_arguments(node: object) -> tuple[object, ...]:
    arguments = next(
        (
            child for child in _children(node)
            if isinstance(child, gast.ASTRef) and child.name == 'ARGUMENTS'
        ),
        None,
    )
    if arguments is None:
        return ()
    container = next(iter(_children(arguments)), None)
    return tuple(_children(container))


def _super_initializer_call(
    node: object,
) -> tuple[str, tuple[object, ...]] | None:
    if not isinstance(node, gast.ASTRef) or node.name != 'CALL':
        return None
    children = _children(node)
    primary = children[0] if children else None
    if _identifier(primary) != 'super':
        return None
    suffixes: list[object] = []
    for child in children[1:]:
        suffixes.extend(_children(child) if isinstance(child, list) else [child])
    member = next(
        (
            suffix for suffix in suffixes
            if getattr(suffix, 'name', None) == 'MEMBER_ACCESS'
        ),
        None,
    )
    call = next(
        (
            suffix for suffix in suffixes
            if getattr(suffix, 'name', None) == 'CALL_SUFFIX'
        ),
        None,
    )
    if member is None or call is None:
        return None
    member_name = _identifier(member)
    return (
        member_name or '',
        _call_arguments(call),
    )


def _class_body(node: gast.ASTRef) -> gast.ASTRef | None:
    return next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef) and child.name == 'CLASS_BODY'
        ),
        None,
    )


def _body_items(body: gast.ASTRef) -> list[object]:
    items: list[object] = []
    for child in _children(body):
        if isinstance(child, list):
            items.extend(child)
        elif isinstance(child, (gast.ASTRef, gast.ASTKeyword)):
            items.append(child)
    return items


def _function_signature(node: gast.ASTRef) -> gast.ASTRef | None:
    return next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef)
            and child.name == 'FUNCTION_SIGNATURE'
        ),
        None,
    )


def _function_body(node: gast.ASTRef) -> gast.ASTRef | None:
    return next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef)
            and child.name == 'FUNCTION_BODY'
        ),
        None,
    )


def _function_name(node: gast.ASTRef) -> str | None:
    signature = _function_signature(node)
    return _identifier(signature) if signature is not None else None


def _assignment_parts(
    node: gast.ASTRef,
) -> tuple[object | None, str | None, object | None]:
    target = next(
        (
            child for child in _children(node)
            if isinstance(child, gast.ASTRef) and child.name == 'ASSIGN_TARGET'
        ),
        None,
    )
    value = next(
        (
            child for child in _children(node)
            if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
        ),
        None,
    )
    operators = {
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
    operator = next(
        (
            operators[kind]
            for child in _children(node)
            if (kind := _token_kind(child)) in operators
        ),
        None,
    )
    return target, operator, value


def _self_field_name(target: object) -> str | None:
    current = target
    if getattr(current, 'name', None) == 'ASSIGN_TARGET':
        children = _children(current)
        current = children[0] if children else None

    if getattr(current, 'name', None) != 'POSTFIX_EXPR':
        return None
    children = _children(current)
    primary = children[0] if children else None
    if _identifier(primary) != 'self':
        return None

    suffixes: list[object] = []
    for child in children[1:]:
        suffixes.extend(_children(child) if isinstance(child, list) else [child])
    if len(suffixes) != 1:
        return None
    suffix = suffixes[0]
    if getattr(suffix, 'name', None) != 'MEMBER_ACCESS':
        return None
    return _identifier(suffix)


def _initializer_fields(
    compiler: Compiler,
    class_name: str,
    initializer_node: gast.ASTRef,
    parameters: tuple[object, ...],
    initializer_name: str = '__init__',
) -> tuple[tuple[FieldSpec, ...], tuple[str, tuple[object, ...]] | None]:
    body = _function_body(initializer_node)
    if body is None:
        compiler.error(f'El {initializer_name} de {class_name} no tiene cuerpo')
        return (), None

    parameter_scope = Storage(
        compiler.storage.root,
        parent=compiler.storage,
        scope_name=f'class:{class_name}.{initializer_name}',
        function_scope=True,
    )
    seen_parameters: set[str] = set()
    for parameter in parameters:
        name = getattr(parameter, 'name', '')
        if not name:
            compiler.error(
                f'El {initializer_name} de {class_name} contiene un parametro '
                'sin nombre'
            )
            continue
        if name == 'self':
            compiler.error(
                f'El parametro self de {class_name}.{initializer_name} es '
                'implicito'
            )
            continue
        if name in seen_parameters:
            compiler.error(
                f'El parametro {name} esta duplicado en '
                f'{class_name}.{initializer_name}'
            )
            continue
        seen_parameters.add(name)
        if getattr(parameter, 'is_length', False) or getattr(parameter, 'is_size', False):
            compiler.error(
                f'El {initializer_name} de {class_name} no admite parametros '
                'Len_t/Size_t en esta fase'
            )
            continue
        parameter_scope.add(
            name,
            build_symbol(
                parameter_scope,
                name,
                parameter.type_spec,
                kind='parameter',
            ),
        )

    fields: list[FieldSpec] = []
    seen_fields: set[str] = set()
    parent_call: tuple[str, tuple[object, ...]] | None = None
    for statement in _body_items(body):
        if isinstance(statement, gast.ASTKeyword):
            if _token_value(statement) == 'pass':
                continue
            compiler.error(
                f'El {initializer_name} de {class_name} solo admite '
                'asignaciones a self.<campo>'
            )
            continue

        parsed_parent_call = _super_initializer_call(statement)
        if parsed_parent_call is not None:
            if parent_call is not None:
                compiler.error(
                    f'El {initializer_name} de {class_name} solo puede llamar '
                    'una vez al iniciador del padre'
                )
            else:
                parent_call = parsed_parent_call
            continue

        if not isinstance(statement, gast.ASTRef) or statement.name != 'VAR_ASSIGNATION':
            compiler.error(
                f'El {initializer_name} de {class_name} solo admite '
                'super.<iniciador>(...) y asignaciones directas a self.<campo>'
            )
            continue

        target, operator, value_node = _assignment_parts(statement)
        field_name = _self_field_name(target)
        if field_name is None:
            compiler.error(
                f'El {initializer_name} de {class_name} solo puede asignar a '
                'self.<campo>'
            )
            continue
        if operator != '=':
            compiler.error(
                f'La inicializacion de {class_name}.{field_name} en '
                f'{initializer_name} debe usar ='
            )
            continue
        if field_name in seen_fields:
            compiler.error(
                f'El atributo {class_name}.{field_name} ya fue inicializado'
            )
            continue
        if value_node is None:
            compiler.error(
                f'El atributo {class_name}.{field_name} no tiene valor inicial'
            )
            continue

        try:
            value_info = infer_value(
                value_node,
                parameter_scope.resolve,
                compiler.function_lookup,
            )
        except (UnsupportedExpressionError, ValueResolutionError) as error:
            compiler.error(f'{class_name}.{field_name}: {error}')
            continue

        if value_info.type_spec.name in {'void', 'Never'} and not value_info.type_spec.pointer_level:
            compiler.error(
                f'El atributo {class_name}.{field_name} no puede ser '
                f'{value_info.type_spec.name}'
            )
            continue

        seen_fields.add(field_name)
        fields.append(
            FieldSpec(
                field_name,
                value_info.type_spec,
                value_info,
                initializer_node=value_node,
            )
        )

    return tuple(fields), parent_call


def validate(compiler: Compiler, node: gast.ASTRef):
    """Build the struct-backed layout and initializer metadata for a class."""
    symbol = compiler.type_bindings.get(id(node))
    if not isinstance(symbol, AggregateSymbol):
        return node

    from core.frontend.tools import function as function_tools

    decorators = function_tools._decorator_names(node)
    seen_decorators: set[str] = set()
    for decorator in decorators:
        if decorator not in _CLASS_DECORATORS:
            compiler.error(
                f'El decorador @{decorator} no existe para la clase '
                f'{symbol.name}'
            )
        elif decorator in seen_decorators:
            compiler.error(
                f'El decorador @{decorator} esta repetido en la clase '
                f'{symbol.name}'
            )
        seen_decorators.add(decorator)
    symbol.is_frozen = 'frozen' in decorators

    body = _class_body(node)
    if body is None:
        compiler.error(f'La clase {symbol.name} no tiene cuerpo')
        return node

    parent_names = _class_parent_names(node)
    symbol.parent_type = None
    symbol.inherited_fields = ()
    symbol.parent_initializer_name = None
    symbol.parent_initializer_arguments = ()
    if len(parent_names) > 1:
        compiler.error(
            f'La clase {symbol.name} solo puede heredar de una clase'
        )
    elif parent_names:
        parent_name = parent_names[0]
        if parent_name == symbol.name:
            compiler.error(
                f'La clase {symbol.name} no puede heredar de si misma'
            )
        else:
            symbol.parent_type = parent_name

    initializer_node: gast.ASTRef | None = None
    initializer_name: str | None = None
    for item in _body_items(body):
        if isinstance(item, gast.ASTKeyword):
            if _token_value(item) == 'pass':
                continue
            compiler.error(
                f'La clase {symbol.name} solo admite funciones y un iniciador '
                '(__init__ o __frontend__)'
            )
            continue
        if not isinstance(item, gast.ASTRef):
            compiler.error(
                f'La clase {symbol.name} solo admite funciones y un iniciador '
                '(__init__ o __frontend__)'
            )
            continue
        if item.name == 'VAR':
            compiler.error(
                f'La clase {symbol.name} debe declarar sus atributos dentro de '
                '__init__ o __frontend__ mediante self.<campo>'
            )
            continue
        if item.name != 'FUNCTION':
            compiler.error(
                f'La clase {symbol.name} solo admite funciones y un iniciador '
                '(__init__ o __frontend__)'
            )
            continue
        candidate_name = _function_name(item)
        if candidate_name not in _INITIALIZER_NAMES:
            continue
        if initializer_node is not None:
            compiler.error(
                f'La clase {symbol.name} solo puede especificar un iniciador '
                '(__init__ o __frontend__)'
            )
            continue
        initializer_node = item
        initializer_name = candidate_name

    if initializer_node is None or initializer_name is None:
        # A class without an initializer remains a nominal empty struct for
        # now, but cannot be constructed through either initializer hook.
        symbol.constructor_parameters = None
        symbol.initializer_name = None
        symbol.fields = ()
        return node

    try:
        function_name, signature = function_tools.signature_from_node(
            initializer_node,
            pointer_size=compiler.storage.pointer_size,
        )
    except TypeResolutionError as error:
        compiler.error(f'{symbol.name}.{initializer_name}: {error}')
        return node

    if function_name != initializer_name:
        compiler.error(
            f'La clase {symbol.name} contiene un {initializer_name} invalido'
        )
        return node
    initializer_decorators = function_tools._decorator_names(initializer_node)
    if initializer_decorators:
        compiler.error(
            f'El iniciador {symbol.name}.{initializer_name} no admite '
            'decoradores'
        )
    if initializer_name == '__frontend__':
        visible_parameters = [
            parameter for parameter in signature.parameters
            if not (
                getattr(parameter, 'is_length', False)
                or getattr(parameter, 'is_size', False)
            )
        ]
        if len(visible_parameters) != 1 or len(visible_parameters) != len(
            signature.parameters
        ):
            compiler.error(
                f'{symbol.name}.__frontend__ debe recibir exactamente un '
                'parametro de entrada'
            )
    return_type = signature.return_type
    if (
        return_type.name != 'void'
        or return_type.pointer_level
        or return_type.array_depth
    ):
        compiler.error(f'{symbol.name}.{initializer_name} debe retornar void')

    symbol.constructor_parameters = signature.parameters
    symbol.initializer_name = initializer_name
    symbol.fields, parent_call = _initializer_fields(
        compiler,
        symbol.name,
        initializer_node,
        signature.parameters,
        initializer_name,
    )
    if parent_call is not None:
        symbol.parent_initializer_name, symbol.parent_initializer_arguments = (
            parent_call
        )
    return node


def _initializer_parameter_scope(
    compiler: Compiler,
    symbol: AggregateSymbol,
) -> Storage:
    scope = Storage(
        compiler.storage.root,
        parent=compiler.storage,
        scope_name=f'class:{symbol.name}.{symbol.initializer_name or "initializer"}',
        function_scope=True,
    )
    for parameter in symbol.constructor_parameters or ():
        if getattr(parameter, 'is_length', False) or getattr(parameter, 'is_size', False):
            continue
        name = getattr(parameter, 'name', '')
        if name:
            scope.add(
                name,
                build_symbol(
                    scope,
                    name,
                    parameter.type_spec,
                    kind='parameter',
                ),
            )
    return scope


def _validate_parent_initializer_call(
    compiler: Compiler,
    child: AggregateSymbol,
    parent: AggregateSymbol,
) -> None:
    parent_name = parent.initializer_name
    call_name = child.parent_initializer_name
    if parent_name is None:
        if call_name is not None:
            compiler.error(
                f'La clase {parent.name} no tiene un iniciador para '
                f'super.{call_name}(...)'
            )
        return

    if child.initializer_name is None:
        compiler.error(
            f'La clase {child.name} debe declarar un iniciador y llamar a '
            f'super.{parent_name}(...)'
        )
        return
    if call_name is None:
        compiler.error(
            f'El iniciador {child.name}.{child.initializer_name} debe llamar a '
            f'super.{parent_name}(...)'
        )
        return
    if call_name != parent_name:
        compiler.error(
            f'El iniciador {child.name}.{child.initializer_name} debe llamar a '
            f'super.{parent_name}(...), no a super.{call_name}(...)'
        )
        return

    parameters = [
        parameter for parameter in parent.constructor_parameters or ()
        if not (
            getattr(parameter, 'is_length', False)
            or getattr(parameter, 'is_size', False)
        )
    ]
    arguments = child.parent_initializer_arguments
    if len(arguments) != len(parameters):
        compiler.error(
            f'super.{parent_name} de {child.name} esperaba '
            f'{len(parameters)} argumentos y recibio {len(arguments)}'
        )
        return

    scope = _initializer_parameter_scope(compiler, child)
    for parameter, argument in zip(parameters, arguments):
        try:
            argument_info = infer_value(
                argument,
                scope.resolve,
                compiler.function_lookup,
            )
        except (UnsupportedExpressionError, ValueResolutionError) as error:
            compiler.error(
                f'super.{parent_name} de {child.name}: {error}'
            )
            continue
        if not is_compatible(parameter.type_spec, argument_info):
            compiler.error(
                f'El argumento de super.{parent_name} en {child.name} no '
                f'coincide con {parameter.type_spec.canonical_name}'
            )


def validate_inheritance(compiler: Compiler, nodes: list[gast.ASTRef]) -> None:
    """Validate parent links and flatten inherited field metadata."""
    classes = [
        compiler.type_bindings.get(id(node))
        for node in nodes
        if node.name == 'CLASS'
    ]
    classes = [
        symbol for symbol in classes
        if isinstance(symbol, AggregateSymbol) and symbol.is_class
    ]

    parents: dict[str, AggregateSymbol | None] = {}
    for symbol in classes:
        compiler.activate_module(symbol.module_path)
        parent = (
            compiler.storage.resolve_type(symbol.parent_type)
            if symbol.parent_type
            else None
        )
        if symbol.parent_type and not isinstance(parent, AggregateSymbol):
            compiler.error(
                f'La clase padre {symbol.parent_type} de {symbol.name} no existe'
            )
            symbol.parent_type = None
        elif symbol.parent_type and not parent.is_class:
            compiler.error(
                f'La clase {symbol.name} solo puede heredar de otra class; '
                f'{symbol.parent_type} no lo es'
            )
            symbol.parent_type = None
            parent = None
        elif parent is not None:
            if symbol.is_frozen and not parent.is_frozen:
                compiler.error(
                    f'La clase @frozen {symbol.name} solo puede heredar de '
                    f'otra clase @frozen ({parent.name})'
                )
            elif parent.is_frozen and not symbol.is_frozen:
                compiler.error(
                    f'La clase {symbol.name} que hereda de la clase @frozen '
                    f'{parent.name} tambien debe ser @frozen'
                )
            if symbol.is_packed and not parent.is_packed:
                compiler.error(
                    f'La clase {symbol.name} no puede ser @packed si su padre '
                    f'{parent.name} no lo es'
                )
                symbol.is_packed = False
            elif parent.is_packed:
                symbol.is_packed = True
            if parent.alignment is not None and (
                symbol.alignment is None
                or symbol.alignment < parent.alignment
            ):
                symbol.alignment = parent.alignment
        parents[symbol.name] = parent

    state: dict[str, int] = {}
    stack: list[str] = []
    reported_cycles: set[tuple[str, ...]] = set()

    def flatten(symbol: AggregateSymbol) -> tuple[FieldSpec, ...]:
        status = state.get(symbol.name, 0)
        if status == 2:
            return symbol.all_fields
        if status == 1:
            start = stack.index(symbol.name)
            cycle = tuple((*stack[start:], symbol.name))
            if cycle not in reported_cycles:
                reported_cycles.add(cycle)
                compiler.error(
                    f'Ciclo de herencia detectado: {" -> ".join(cycle)}'
                )
            symbol.inherited_fields = ()
            return symbol.fields

        state[symbol.name] = 1
        stack.append(symbol.name)
        parent = parents.get(symbol.name)
        inherited = flatten(parent) if parent is not None else ()
        symbol.inherited_fields = inherited
        stack.pop()
        state[symbol.name] = 2

        inherited_names = {field.name for field in inherited}
        collisions = [
            field.name for field in symbol.fields
            if field.name in inherited_names
        ]
        if collisions:
            for field_name in collisions:
                compiler.error(
                    f'El campo {symbol.name}.{field_name} ya existe en su clase padre'
                )
            symbol.fields = tuple(
                field for field in symbol.fields
                if field.name not in inherited_names
            )
        return symbol.all_fields

    for symbol in classes:
        compiler.activate_module(symbol.module_path)
        flatten(symbol)

    for symbol in classes:
        compiler.activate_module(symbol.module_path)
        parent = parents.get(symbol.name)
        if parent is not None:
            _validate_parent_initializer_call(compiler, symbol, parent)


def _method_decorators(
    compiler: Compiler,
    method_name: str,
    decorators: tuple[str, ...],
) -> None:
    allowed = {'static', 'unsafe', 'assembler', 'after'}
    seen: set[str] = set()
    for decorator in decorators:
        magic_name = method_name.rsplit('.', 1)[-1]
        if decorator not in allowed:
            compiler.error(
                f'El decorador @{decorator} no existe para el metodo '
                f'{method_name}'
            )
        elif decorator == 'after' and magic_name not in {
            '__ongetter__',
            '__onsetter__',
        }:
            compiler.error(
                f'El decorador @after solo puede usarse en los hooks de acceso: '
                f'{method_name}'
            )
        elif decorator in seen:
            compiler.error(
                f'El decorador @{decorator} esta repetido en {method_name}'
            )
        seen.add(decorator)


def _bind_method_context(
    compiler: Compiler,
    symbol: FunctionSymbol,
    class_symbol: AggregateSymbol,
) -> None:
    """Expose the implicit instance context without adding a source parameter."""
    scope = symbol.scope
    if scope is None or symbol.is_static:
        return

    receiver = build_symbol(
        scope,
        'self',
        TypeSpec(class_symbol.name),
        kind='receiver',
    )
    receiver.is_receiver = True
    if not scope.add('self', receiver):
        compiler.error(
            f'El metodo {symbol.source_name or symbol.name} no puede declarar '
            'un parametro llamado self'
        )


def collect_methods(compiler: Compiler, nodes: list[gast.ASTRef]) -> None:
    """Register class methods after class fields and initializers are known."""
    from core.frontend.tools import function as function_tools

    for node in nodes:
        if node.name != 'CLASS':
            continue

        compiler.activate_module(compiler.module_for_node(node))

        class_symbol = compiler.type_bindings.get(id(node))
        if not isinstance(class_symbol, AggregateSymbol):
            continue
        body = _class_body(node)
        if body is None:
            continue

        for item in _body_items(body):
            if not isinstance(item, gast.ASTRef) or item.name != 'FUNCTION':
                continue
            source_name = _function_name(item)
            if not source_name or source_name in _INITIALIZER_NAMES:
                continue

            try:
                parsed_name, source_signature = function_tools.signature_from_node(
                    item,
                    pointer_size=compiler.storage.pointer_size,
                )
            except TypeResolutionError as error:
                compiler.error(f'{class_symbol.name}: {error}')
                continue

            if parsed_name != source_name:
                compiler.error(
                    f'El metodo de {class_symbol.name} no tiene un nombre valido'
                )
                continue

            decorators = function_tools._decorator_names(item)
            method_name = f'{class_symbol.name}.{source_name}'
            _method_decorators(compiler, method_name, decorators)
            function_tools.validate_magic_method_signature(
                compiler,
                class_symbol.name,
                source_name,
                source_signature,
                decorators,
            )
            is_static = 'static' in decorators

            parameters = source_signature.parameters
            if is_static:
                method_signature = source_signature
                receiver_name = None
            else:
                receiver_name = '__self'
                receiver = ParameterSpec(
                    name=receiver_name,
                    type_spec=TypeSpec(class_symbol.name, pointer_level=1),
                    is_receiver=True,
                )
                method_signature = FunctionSignature(
                    parameters=(receiver, *parameters),
                    return_type=source_signature.return_type,
                )

            symbol = FunctionSymbol(
                f'{class_symbol.name}__{source_name}',
                method_signature,
                decorators=decorators,
                is_inline=function_tools._is_inline(item),
                owner_type=class_symbol.name,
                source_name=source_name,
                is_method=True,
                is_static=is_static,
                receiver_name=receiver_name,
                module_path=compiler.module_for_node(node),
                privacy=function_tools._privacy(item),
            )
            if not compiler.storage.define_method(symbol):
                compiler.error(f'El metodo ya fue declarado: {method_name}')
                continue

            compiler.function_bindings[id(item)] = symbol
            function_tools._validate_bit_width(
                compiler,
                symbol.name,
                source_signature.return_type,
            )
            _bind_method_context(compiler, symbol, class_symbol)
            function_tools._bind_parameters(compiler, symbol)


def process_methods(compiler: Compiler, nodes: list[gast.ASTRef]) -> None:
    """Run the regular function semantic pass over every class method body."""
    from core.frontend.tools import function as function_tools

    for node in nodes:
        if node.name != 'CLASS':
            continue
        body = _class_body(node)
        if body is None:
            continue
        for item in _body_items(body):
            if (
                isinstance(item, gast.ASTRef)
                and item.name == 'FUNCTION'
                and id(item) in compiler.function_bindings
            ):
                function_tools.process(compiler, item)


__all__ = [
    'collect_methods',
    'process_methods',
    'validate',
    'validate_inheritance',
]

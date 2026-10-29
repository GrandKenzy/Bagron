from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from core.frontend.handles import handle_declaration
from core.frontend.objects import AggregateSymbol, FieldSpec, TypeSpec
from core.frontend.syntax.keywords import INTRINSIC_TYPES
from core.frontend.tools.types import (
    INTEGER_TYPES,
    TypeResolutionError,
    UnsupportedExpressionError,
    ValueResolutionError,
    infer_value,
    is_compatible,
    resolve_type,
)
from gram import ast as gast

if TYPE_CHECKING:
    from core.compiler import Compiler


_FLAGS_BASE_TYPES = {
    'int8', 'int16', 'int32', 'int64',
    'uint8', 'uint16', 'uint32', 'uint64',
}
_INTEGER_WIDTHS = {
    'int': 32,
    'int8': 8,
    'int16': 16,
    'int32': 32,
    'int64': 64,
    'uint': 32,
    'uint8': 8,
    'uint16': 16,
    'uint32': 32,
    'uint64': 64,
    'byte': 8,
}
_AGGREGATE_DECORATORS = {'packed', 'order_lsb', 'order_msb'}


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


def _find_identifier(node: object) -> str | None:
    if _token_kind(node) == 'IDENT':
        return str(_token_value(node))
    for child in _children(node):
        found = _find_identifier(child)
        if found is not None:
            return found
    return None


def _find_all(node: object, names: set[str]) -> Iterable[gast.ASTRef]:
    if isinstance(node, gast.ASTRef):
        if node.name in names:
            yield node
        for child in node.nodes:
            yield from _find_all(child, names)
    elif isinstance(node, list):
        for child in node:
            yield from _find_all(child, names)


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


def _signature(node: gast.ASTRef) -> gast.ASTRef | None:
    return next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef)
            and child.name.endswith('_SIGNATURE')
        ),
        None,
    )


def _body(node: gast.ASTRef) -> gast.ASTRef | None:
    return next(
        (
            child for child in node.nodes
            if isinstance(child, gast.ASTRef)
            and child.name.endswith('_BODY')
        ),
        None,
    )


def _contains_token(node: object, value: str) -> bool:
    if _token_value(node) == value:
        return True
    return any(_contains_token(child, value) for child in _children(node))


def _decorator_name(node: object) -> str | None:
    values: list[str] = []

    def collect(current: object) -> None:
        value = _token_value(current)
        if isinstance(value, str) and value != '@':
            values.append(value)
        for child in _children(current):
            collect(child)

    collect(node)
    return values[-1] if values else None


def _decorator_names(node: gast.ASTRef) -> tuple[str, ...]:
    names: list[str] = []
    for decorator in _find_all(node, {'AGGREGATE_DECORATOR'}):
        name = _decorator_name(decorator)
        if name is not None:
            names.append(name)
    return tuple(names)


def _flags_base_node(signature: gast.ASTRef) -> object | None:
    """Return the TYPE node/list positioned after a flags declaration name."""
    found_name = False
    for child in _children(signature):
        if not found_name:
            if _token_kind(child) == 'IDENT':
                found_name = True
            continue
        if _token_value(child) == ':':
            break
        if isinstance(child, gast.ASTRef) and child.name == 'TYPE':
            return child
        if isinstance(child, list) and child:
            return child
    return None


def _flags_base_type(
    compiler: Compiler,
    signature: gast.ASTRef,
    name: str,
) -> TypeSpec | None:
    node = _flags_base_node(signature)
    if node is None:
        compiler.error(f'El flags {name} requiere un tipo base explicito')
        return None
    try:
        type_spec = resolve_type(node)
    except TypeResolutionError as error:
        compiler.error(f'El tipo base de flags {name} es invalido: {error}')
        return None
    if (
        type_spec.name not in _FLAGS_BASE_TYPES
        or type_spec.pointer_level
        or type_spec.array_depth
        or type_spec.value_is_const
    ):
        compiler.error(
            f'El tipo base de flags {name} debe ser int8/16/32/64 o '
            'uint8/16/32/64 sin punteros ni constancia'
        )
        return None
    return type_spec


def _alignment_payload(node: gast.ASTRef) -> object | None:
    children = _children(node)
    if len(children) < 2:
        return None
    return children[-1]


def _alignment_metadata(
    compiler: Compiler,
    node: gast.ASTRef,
    name: str,
) -> tuple[int | None, TypeSpec | None]:
    attributes = list(_find_all(node, {'ALIGNEMENT'}))
    if len(attributes) > 1:
        compiler.error(f'El tipo {name} solo puede declarar un __align__')
        return None, None
    if not attributes:
        return None, None

    payload = _alignment_payload(attributes[0])
    if payload is None:
        compiler.error(f'El __align__ de {name} no tiene valor')
        return None, None
    if _token_kind(payload) == 'NUMBER':
        try:
            alignment = int(_token_value(payload))
        except (TypeError, ValueError):
            alignment = 0
        if (
            alignment < 1
            or alignment > 64
            or alignment & (alignment - 1)
        ):
            compiler.error(
                f'El __align__ de {name} debe ser una potencia de dos entre 1 y 64'
            )
            return None, None
        return alignment, None

    try:
        type_spec = resolve_type(payload)
    except TypeResolutionError as error:
        compiler.error(f'El __align__ de {name} es invalido: {error}')
        return None, None
    if (
        type_spec.name not in INTRINSIC_TYPES
        or type_spec.name in {'void', 'Null', 'chain', 'callptr'}
        or type_spec.pointer_level
        or type_spec.array_depth
    ):
        compiler.error(
            f'El __align__ de {name} debe usar un escalar intrinseco o un numero'
        )
        return None, None
    return None, type_spec


def _declaration_metadata(
    compiler: Compiler,
    node: gast.ASTRef,
    signature: gast.ASTRef,
    name: str,
) -> tuple[bool, bool, int | None, TypeSpec | None, str]:
    decorators = _decorator_names(node)
    seen: set[str] = set()
    for decorator in decorators:
        if decorator not in _AGGREGATE_DECORATORS:
            compiler.error(f'El decorador @{decorator} no existe para {name}')
        elif decorator in seen:
            compiler.error(f'El decorador @{decorator} esta repetido en {name}')
        seen.add(decorator)

    kind = node.name.lower()
    orders = [item for item in decorators if item in {'order_lsb', 'order_msb'}]
    if orders and kind != 'flags':
        compiler.error(f'@{orders[0]} solo puede usarse con flags ({name})')
    if len(orders) > 1:
        compiler.error(f'{name} no puede combinar @order_lsb y @order_msb')

    alignment, alignment_type = _alignment_metadata(compiler, node, name)
    return (
        'packed' in decorators,
        _contains_token(signature, 'volatile'),
        alignment,
        alignment_type,
        'msb' if 'order_msb' in decorators else 'lsb',
    )


def _register_node(compiler: Compiler, node: gast.ASTRef) -> None:
    signature = _signature(node)
    name = _find_identifier(signature) if signature is not None else None
    if not name or signature is None:
        compiler.error(f'La declaracion {node.name.lower()} no tiene nombre')
        return

    packed, volatile, alignment, alignment_type, bit_order = _declaration_metadata(
        compiler,
        node,
        signature,
        name,
    )
    base_type = (
        _flags_base_type(compiler, signature, name)
        if node.name == 'FLAGS'
        else None
    )
    symbol = AggregateSymbol(
        name=name,
        kind=node.name.lower(),
        privacy=_privacy(signature),
        base_type=base_type,
        is_packed=packed,
        is_volatile=volatile,
        alignment=alignment,
        alignment_type=alignment_type,
        bit_order=bit_order,
    )
    if not compiler.storage.define_type(symbol):
        compiler.error(f'El tipo ya fue declarado: {name}')
        return
    compiler.type_bindings[id(node)] = symbol


def collect(compiler: Compiler, nodes: list[gast.ASTRef]) -> None:
    """Register aggregate names before any field is validated."""
    for node in nodes:
        if node.name in ('STRUCT', 'MOLD', 'FLAGS'):
            _register_node(compiler, node)


def _known_field_type(compiler: Compiler, type_spec: TypeSpec) -> bool:
    if type_spec.name in INTRINSIC_TYPES:
        if type_spec.name == 'void':
            return type_spec.pointer_level > 0 and type_spec.array_depth == 0
        return type_spec.name not in {'void', 'Null'}
    return compiler.storage.resolve_type(type_spec.name) is not None


def _field_nodes(body: gast.ASTRef) -> list[gast.ASTRef]:
    return list(_find_all(body, {'VAR_INITIALIZATION', 'VAR_DECLARATION'}))


def _resolve_field_type(
    compiler: Compiler,
    handle,
    owner: str,
) -> TypeSpec | None:
    try:
        type_spec = resolve_type(
            handle.type_node,
            pointer_level=handle.pointer_level,
            pointer_is_const=handle.pointer_is_const,
        )
    except TypeResolutionError as error:
        compiler.error(f'{owner}.{handle.name}: {error}')
        return None

    if not _known_field_type(compiler, type_spec):
        compiler.error(
            f'El tipo de {owner}.{handle.name} no existe: '
            f'{type_spec.canonical_name}'
        )
        return None
    return type_spec


def _field_width(type_spec: TypeSpec) -> int | None:
    if type_spec.name in {'Bint', 'uBint'}:
        return type_spec.bit_width
    return _INTEGER_WIDTHS.get(type_spec.name)


def _validate_flags_value(
    compiler: Compiler,
    owner: str,
    handle,
    type_spec: TypeSpec,
):
    if (
        type_spec.pointer_level
        or type_spec.array_depth
        or type_spec.name not in INTEGER_TYPES
    ):
        compiler.error(
            f'El campo {owner}.{handle.name} debe usar un tipo entero escalar'
        )
        return None

    try:
        value_info = infer_value(handle.value_node, compiler.storage.resolve)
    except (UnsupportedExpressionError, ValueResolutionError) as error:
        compiler.error(f'{owner}.{handle.name}: {error}')
        return None

    if not value_info.is_literal or value_info.type_spec.name != 'int':
        compiler.error(
            f'El valor de {owner}.{handle.name} debe ser un literal entero'
        )
        return None

    if not is_compatible(type_spec, value_info):
        compiler.error(
            f'El valor de {owner}.{handle.name} no coincide con '
            f'{type_spec.canonical_name}'
        )
        return None
    return value_info


def validate(compiler: Compiler, node: gast.ASTRef):
    """Validate fields and make aggregate layout fully semantic."""
    symbol = compiler.type_bindings.get(id(node))
    if not isinstance(symbol, AggregateSymbol):
        return node

    body = _body(node)
    if body is None:
        compiler.error(f'El tipo {symbol.name} no tiene cuerpo')
        return node

    fields: list[FieldSpec] = []
    seen: set[str] = set()
    expected = 'VAR_DECLARATION' if symbol.kind == 'flags' else 'VAR_INITIALIZATION'

    for declaration in _field_nodes(body):
        handle = handle_declaration(declaration)
        if handle is None or not handle.name:
            compiler.error(f'El tipo {symbol.name} contiene un campo invalido')
            continue
        if handle.name in seen:
            compiler.error(f'El campo {symbol.name}.{handle.name} ya fue declarado')
            continue
        seen.add(handle.name)

        if declaration.name != expected:
            compiler.error(
                f'El tipo {symbol.kind} {symbol.name} no permite inicializadores '
                f'en sus campos'
            )
            continue

        type_spec = _resolve_field_type(compiler, handle, symbol.name)
        if type_spec is None:
            continue
        if type_spec.name == 'chain':
            compiler.error(
                f'El campo {symbol.name}.{handle.name} no puede usar chain; '
                'un chain requiere un literal propio'
            )
            continue
        if type_spec.array_depth and any(
            length is None for length in type_spec.array_lengths
        ):
            compiler.error(
                f'El array {symbol.name}.{handle.name} debe declarar todos sus tamanos'
            )
            continue

        value_info = None
        if symbol.kind == 'flags':
            value_info = _validate_flags_value(
                compiler, symbol.name, handle, type_spec
            )
            if value_info is None:
                continue
            if _field_width(type_spec) is None:
                compiler.error(
                    f'El campo {symbol.name}.{handle.name} no tiene ancho de bits'
                )
                continue
        fields.append(FieldSpec(handle.name, type_spec, value_info))

    if not fields:
        compiler.error(f'El tipo {symbol.name} no puede estar vacio')
        symbol.fields = ()
        return node

    if symbol.kind == 'flags':
        if symbol.base_type is None:
            compiler.error(f'El flags {symbol.name} no tiene tipo base valido')
            symbol.fields = tuple(fields)
            return node
        base_width = _INTEGER_WIDTHS[symbol.base_type.name]
        total_width = sum(_field_width(field.type_spec) or 0 for field in fields)
        if total_width > base_width:
            compiler.error(
                f'Los campos de flags {symbol.name} ocupan {total_width} bits, '
                f'pero {symbol.base_type.name} solo admite {base_width}'
            )
        if symbol.bit_order == 'msb':
            offset = base_width
            laid_out: list[FieldSpec] = []
            for field in fields:
                width = _field_width(field.type_spec) or 0
                offset -= width
                laid_out.append(FieldSpec(
                    field.name,
                    field.type_spec,
                    field.value_info,
                    bit_offset=offset,
                ))
            fields = laid_out
        else:
            offset = 0
            laid_out = []
            for field in fields:
                width = _field_width(field.type_spec) or 0
                laid_out.append(FieldSpec(
                    field.name,
                    field.type_spec,
                    field.value_info,
                    bit_offset=offset,
                ))
                offset += width
            fields = laid_out

    symbol.fields = tuple(fields)
    return node


def validate_value_cycles(compiler: Compiler) -> None:
    """Reject recursive aggregate layout while allowing pointer recursion."""
    aggregates = {
        name: symbol
        for name, symbol in compiler.storage.types.items()
        if isinstance(symbol, AggregateSymbol)
    }
    graph: dict[str, list[str]] = {name: [] for name in aggregates}
    for name, symbol in aggregates.items():
        for field in symbol.fields:
            if field.type_spec.pointer_level:
                continue
            target = aggregates.get(field.type_spec.name)
            if target is not None:
                graph[name].append(target.name)

    visiting: list[str] = []
    visited: set[str] = set()
    reported: set[tuple[str, ...]] = set()

    def visit(name: str) -> None:
        if name in visiting:
            cycle = tuple((*visiting[visiting.index(name):], name))
            if cycle not in reported:
                reported.add(cycle)
                compiler.error('Ciclo de agregados por valor: ' + ' -> '.join(cycle))
            return
        if name in visited:
            return
        visiting.append(name)
        for target in graph[name]:
            visit(target)
        visiting.pop()
        visited.add(name)

    for name in graph:
        visit(name)


__all__ = ['collect', 'validate', 'validate_value_cycles']

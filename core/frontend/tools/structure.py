from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from core.frontend.handles import handle_declaration
from core.frontend.objects import AggregateSymbol, DefinedIntegerSymbol, FieldSpec, TypeSpec
from core.frontend.syntax.keywords import INTRINSIC_TYPES
from core.frontend.tools.types import (
    TypeResolutionError,
    bind_nominal_type,
    resolve_type,
)
from core.frontend.tools.opaque import validate_opaque_use
from gram import ast as gast

if TYPE_CHECKING:
    from core.compiler import Compiler


_AGGREGATE_DECORATORS = {'packed', 'align'}


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
        if (
            isinstance(value, str)
            and value not in {'@', '(', ')'}
            and _token_kind(current) != 'NUMBER'
        ):
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


def _alignment_payload(node: gast.ASTRef) -> object | None:
    if _token_kind(node) == 'NUMBER':
        return node
    for child in _children(node):
        payload = _alignment_payload(child)
        if payload is not None:
            return payload
    return None


def _alignment_metadata(
    compiler: Compiler,
    node: gast.ASTRef,
    name: str,
) -> int | None:
    attributes = list(_find_all(node, {'ALIGNMENT'}))
    if len(attributes) > 1:
        compiler.error(f'El tipo {name} solo puede declarar un @align')
        return None
    if not attributes:
        return None

    payload = _alignment_payload(attributes[0])
    if payload is None:
        compiler.error(f'El decorador @align de {name} no tiene valor')
        return None
    try:
        alignment = int(_token_value(payload))
    except (TypeError, ValueError):
        alignment = 0
    if alignment < 1 or alignment > 64 or alignment & (alignment - 1):
        compiler.error(
            f'El @align de {name} debe ser una potencia de dos entre 1 y 64'
        )
        return None
    return alignment


def _declaration_metadata(
    compiler: Compiler,
    node: gast.ASTRef,
    signature: gast.ASTRef,
    name: str,
) -> tuple[bool, bool, int | None, bool]:
    decorators = _decorator_names(node)
    seen: set[str] = set()
    for decorator in decorators:
        allowed = {'signed'} if node.name == 'FIELDS' else _AGGREGATE_DECORATORS
        if decorator not in allowed:
            compiler.error(f'El decorador @{decorator} no existe para {name}')
        elif decorator in seen:
            compiler.error(f'El decorador @{decorator} esta repetido en {name}')
        seen.add(decorator)

    alignment = _alignment_metadata(compiler, node, name)
    return (
        'packed' in decorators,
        _contains_token(signature, 'volatile'),
        alignment,
        'signed' in decorators,
    )


def _register_node(compiler: Compiler, node: gast.ASTRef) -> None:
    signature = _signature(node)
    name = _find_identifier(signature) if signature is not None else None
    if not name or signature is None:
        compiler.error(f'La declaracion {node.name.lower()} no tiene nombre')
        return

    packed, volatile, alignment, signed_fields = _declaration_metadata(
        compiler,
        node,
        signature,
        name,
    )
    base_type = None
    # A class starts as a struct-backed type.  Keeping the nominal kind as
    # ``struct`` lets the existing field validation and LLVM layout code serve
    # classes without introducing object/lifetime semantics yet.
    kind = 'struct' if node.name == 'CLASS' else node.name.lower()
    symbol = AggregateSymbol(
        name=name,
        kind=kind,
        is_class=node.name == 'CLASS',
        privacy=_privacy(signature),
        base_type=base_type,
        is_packed=packed,
        is_volatile=volatile,
        alignment=alignment,
        signed_fields=signed_fields,
        module_path=compiler.module_for_node(node),
    )
    if kind == 'fields' and any(
        isinstance(existing, DefinedIntegerSymbol)
        for existing in compiler.storage.type_candidates.get(name, ())
    ):
        compiler.error(
            f'El tipo fields {name} colisiona con un entero definido del mismo nombre'
        )
        return
    if not compiler.storage.define_type(symbol):
        compiler.error(f'El tipo ya fue declarado: {name}')
        return
    compiler.type_bindings[id(node)] = symbol


def collect(compiler: Compiler, nodes: list[gast.ASTRef]) -> None:
    """Register aggregate names before any field is validated."""
    for node in nodes:
        if node.name in ('CLASS', 'STRUCT', 'MOLD', 'FIELDS'):
            _register_node(compiler, node)


def _known_field_type(compiler: Compiler, type_spec: TypeSpec) -> bool:
    if type_spec.name in INTRINSIC_TYPES:
        if type_spec.name == 'Never':
            return False
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
    *,
    allow_bit_types: bool = False,
) -> TypeSpec | None:
    try:
        type_spec = resolve_type(
            handle.type_node,
            pointer_level=handle.pointer_level,
            pointer_is_const=handle.pointer_is_const,
            pointer_size=compiler.storage.pointer_size,
            allow_bit_types=allow_bit_types,
        )
        type_spec = bind_nominal_type(compiler.storage, type_spec)
    except TypeResolutionError as error:
        compiler.error(f'{owner}.{handle.name}: {error}')
        return None

    try:
        validate_opaque_use(
            compiler.storage,
            type_spec,
            f'El campo {owner}.{handle.name}',
        )
    except TypeResolutionError as error:
        compiler.error(str(error))
        return None

    if not _known_field_type(compiler, type_spec):
        compiler.error(
            f'El tipo de {owner}.{handle.name} no existe: '
            f'{type_spec.canonical_name}'
        )
        return None
    return type_spec


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
    expected = 'VAR_INITIALIZATION'

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

        type_spec = _resolve_field_type(
            compiler,
            handle,
            symbol.name,
            allow_bit_types=symbol.kind == 'fields',
        )
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

        if symbol.kind == 'fields':
            if (
                type_spec.name != 'Bint'
                or type_spec.bit_width is None
                or type_spec.pointer_level
                or type_spec.array_depth
            ):
                compiler.error(
                    f'El campo {symbol.name}.{handle.name} debe usar Bint(n) '
                    'sin punteros ni arrays'
                )
                continue
        fields.append(FieldSpec(handle.name, type_spec))

    if not fields:
        compiler.error(f'El tipo {symbol.name} no puede estar vacio')
        symbol.fields = ()
        return node

    if symbol.kind == 'fields' and symbol.signed_fields:
        # The hidden sign bit is represented by the backend only.  Keeping it
        # out of ``fields`` preserves the source-level limb list and its arity.
        symbol.bit_order = 'signed'

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
        for field in symbol.all_fields:
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

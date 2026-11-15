"""Compile-time ownership states for buffers and opaque descriptors.

The state is semantic metadata only.  It is never lowered to LLVM, stored in
the buffer descriptor, or represented in the generated ABI.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from core.frontend.objects import (
    AggregateSymbol,
    OpaqueSymbol,
    TypeSpec,
    ValueInfo,
    Variable,
)


OWNED = 'owned'
BORROWED = 'borrowed'
DEAD = 'dead'
CLOSED = 'closed'
MOVED = 'moved'
BUFFER_STATES = frozenset({OWNED, BORROWED, DEAD})
# Estos estados aparecen cuando una rama consume el recurso y otra lo conserva.
MAYBE_DEAD = 'maybe_dead'
MAYBE_CLOSED = 'maybe_closed'
MAYBE_MOVED = 'maybe_moved'
RESOURCE_STATES = frozenset({
    OWNED, BORROWED, DEAD, CLOSED, MOVED,
    MAYBE_DEAD, MAYBE_CLOSED, MAYBE_MOVED,
})
# El orden fija qué estado se informa cuando las ramas consumen de forma distinta.
_CONSUMED_STATES = (CLOSED, MOVED, DEAD)
_MAYBE_OF = {DEAD: MAYBE_DEAD, CLOSED: MAYBE_CLOSED, MOVED: MAYBE_MOVED}
_MAYBE_KIND = {maybe: kind for kind, maybe in _MAYBE_OF.items()}
# Estados con los que un recurso sale de su ambito sin haberse consumido en
# todas las rutas.
_LEAK_STATES = frozenset({OWNED, *_MAYBE_OF.values()})


def _children(node: object) -> list[object]:
    """Return direct AST children without importing the frontend walker."""
    if isinstance(node, list):
        return list(node)
    items = getattr(node, 'items', None)
    if items is not None:
        return list(items)
    nodes = getattr(node, 'nodes', None)
    return list(nodes) if nodes is not None else []


def is_buffer_symbol(symbol: object | None) -> bool:
    """Return whether ``symbol`` is one owning/borrowing a dynamic buffer."""
    type_spec = getattr(symbol, 'type_spec', None)
    return bool(
        type_spec is not None
        and getattr(type_spec, 'name', None) == 'buffer'
        and getattr(type_spec, 'pointer_level', 0) == 0
        and getattr(type_spec, 'array_depth', 0) == 0
        and len(getattr(type_spec, 'array_lengths', ())) == 1
    )


def is_opaque_symbol(symbol: object | None) -> bool:
    """Return whether a variable carries a nominal opaque descriptor."""
    return bool(
        symbol is not None
        and getattr(symbol, 'opaque_state', None) in RESOURCE_STATES
    )


def is_resource_symbol(symbol: object | None) -> bool:
    return is_buffer_symbol(symbol) or is_opaque_symbol(symbol)


def _storage(namespace: object) -> object | None:
    owner = getattr(namespace, '__self__', None)
    return getattr(namespace, 'storage', None) or owner


def resource_kind(storage: object | None, type_spec: TypeSpec | None) -> str | None:
    """Classify one direct resource type without creating runtime metadata."""

    if type_spec is None or type_spec.pointer_level or type_spec.array_depth:
        return None
    if type_spec.name == 'buffer' and len(type_spec.array_lengths) == 1:
        return 'buffer'
    resolver = getattr(storage, 'resolve_type', None)
    declared = resolver(type_spec.name) if callable(resolver) else None
    return 'opaque' if isinstance(declared, OpaqueSymbol) else None


def contains_resource_type(
    storage: object | None,
    type_spec: TypeSpec | None,
    seen: set[str] | None = None,
) -> bool:
    """Return whether a value owns a direct or nested resource."""

    if resource_kind(storage, type_spec) is not None:
        return True
    if type_spec is None or type_spec.pointer_level or type_spec.array_depth:
        return False
    resolver = getattr(storage, 'resolve_type', None)
    declared = resolver(type_spec.name) if callable(resolver) else None
    if not isinstance(declared, AggregateSymbol):
        return False
    seen = set() if seen is None else seen
    key = declared.registry_key or declared.name
    if key in seen:
        return False
    seen.add(key)
    return any(
        contains_resource_type(storage, field.type_spec, seen)
        for field in declared.all_fields
    )


def _place_key(symbol: object, path: tuple[tuple[str, object], ...]) -> object:
    if not path and is_resource_symbol(symbol):
        return id(symbol)
    normalized = tuple(
        (kind, '*' if kind == 'index' else value)
        for kind, value in path
    )
    return ('place', id(symbol), normalized)


def _root_symbol(value: object, namespace: Callable[[str], object | None]):
    name = getattr(value, 'identifier', None)
    return namespace(name) if name else None


def state_for_value(
    function: object | None,
    value: ValueInfo,
    namespace: Callable[[str], object | None],
) -> str | None:
    """Read ownership for a root or resource field place."""

    root = _root_symbol(value, namespace)
    if root is None:
        return None
    storage = _storage(namespace)
    if not contains_resource_type(storage, value.type_spec):
        return None
    states = getattr(function, 'buffer_states', {})
    path = value.address_path
    # A moved aggregate root invalidates every resource descendant.
    for count in range(0, len(path) + 1):
        key = _place_key(root, path[:count])
        state = states.get(key)
        if state in {DEAD, CLOSED, MOVED, MAYBE_DEAD, MAYBE_CLOSED, MAYBE_MOVED}:
            return state
    key = _place_key(root, path)
    if key in states:
        return states[key]
    initial = initial_state(root)
    if initial is not None:
        return initial
    return BORROWED if getattr(root, 'scope_kind', None) == 'parameter' else OWNED


def set_state_for_value(
    function: object | None,
    value: ValueInfo,
    namespace: Callable[[str], object | None],
    state: str,
) -> None:
    """Set ownership for the exact place represented by ``value``."""

    root = _root_symbol(value, namespace)
    states = getattr(function, 'buffer_states', None)
    if root is None or states is None:
        return
    states[_place_key(root, value.address_path)] = state


def transfer_resource_value(
    function: object | None,
    target: Variable | ValueInfo,
    source: ValueInfo,
    namespace: Callable[[str], object | None],
    *,
    fresh_target: bool = False,
) -> str | None:
    """Move any direct or aggregate resource value into another place."""

    storage = _storage(namespace)
    target_type = getattr(target, 'type_spec', None)
    if not contains_resource_type(storage, target_type):
        return None
    target_value = target if isinstance(target, ValueInfo) else ValueInfo(
        target.type_spec,
        identifier=target.name,
        is_lvalue=True,
        storage_origin=getattr(target, 'scope_kind', None),
    )
    origin = _root_symbol(source, namespace)
    destination = _root_symbol(target_value, namespace)
    if origin is destination and source.address_path == target_value.address_path:
        return None
    if origin is not None:
        if getattr(origin, 'scope_kind', None) == 'global':
            return (
                f'El recurso global {origin.name} no puede transferirse: su '
                'propiedad no es local a la funcion'
            )
        state = state_for_value(function, source, namespace)
        if state != OWNED:
            return (
                f'El recurso {source.identifier or "<anonimo>"} esta en estado '
                f'{state or "desconocido"}; solo un valor owned puede moverse'
            )
        set_state_for_value(function, source, namespace, MOVED)
    if not fresh_target and getattr(target, 'initialized', True):
        target_state = state_for_value(function, target_value, namespace)
        if target_state == OWNED:
            return (
                f'El destino {target_value.identifier or "<anonimo>"} ya posee '
                'un recurso; consumelo antes de sobrescribirlo'
            )
    set_state_for_value(function, target_value, namespace, OWNED)
    return None


def initial_state(symbol: object | None) -> str | None:
    """Get the state before flow analysis: locals own, parameters borrow."""
    if not is_resource_symbol(symbol):
        return None
    state = (
        getattr(symbol, 'buffer_state', None)
        if is_buffer_symbol(symbol)
        else getattr(symbol, 'opaque_state', None)
    )
    allowed = BUFFER_STATES if is_buffer_symbol(symbol) else RESOURCE_STATES
    if state in allowed:
        return state
    return BORROWED if getattr(symbol, 'scope_kind', None) == 'parameter' else OWNED


def state_for(function: object | None, symbol: object | None) -> str | None:
    """Read a function-local flow state, falling back to its initial state."""
    initial = initial_state(symbol)
    if initial is None:
        return None
    states = getattr(function, 'buffer_states', None)
    if isinstance(states, Mapping):
        return states.get(id(symbol), initial)
    return initial


def set_state(function: object | None, symbol: object | None, state: str) -> None:
    """Record a state transition in semantic metadata only."""
    if state not in RESOURCE_STATES:
        raise ValueError(f'unknown resource ownership state: {state}')
    if not is_resource_symbol(symbol):
        return
    states = getattr(function, 'buffer_states', None)
    if states is None:
        return
    states[id(symbol)] = state


CONSUME_DECORATOR = 'consume'
_LEGACY_CONSUME_PREFIX = 'close_'


def has_consume_decorator(function: object | None) -> bool:
    """Return whether ``function`` is declared with ``@consume``."""
    return CONSUME_DECORATOR in (getattr(function, 'decorators', None) or ())


def has_legacy_consume_name(name: str | None) -> bool:
    """Return whether ``name`` uses the legacy ``close_*`` convention."""
    return bool(name) and str(name).startswith(_LEGACY_CONSUME_PREFIX)


def consumes_opaque_arguments(function: object | None, name: str | None) -> bool:
    """Return whether a call to ``function`` consumes its opaque arguments.

    ``@consume`` is the explicit marker.  The ``close_*`` name remains a
    compatibility path and is the only one available to ``extern`` functions,
    which cannot carry decorators.
    """
    return has_consume_decorator(function) or has_legacy_consume_name(name)


def consume_opaque_argument(
    function: object | None,
    function_name: str,
    parameter: object,
    argument: object,
    namespace: Callable[[str], object | None],
    current_function: object | None,
) -> str | None:
    """Apply the ``@consume`` (or legacy ``close_*``) ownership convention.

    Opaque parameters are borrowed by ordinary calls.  A consuming function
    takes ownership of every opaque argument it receives and leaves the caller
    binding ``closed``.
    """
    type_spec = getattr(parameter, 'type_spec', None)
    if not consumes_opaque_arguments(function, function_name):
        return None
    storage = _storage(namespace)
    if resource_kind(storage, type_spec) != 'opaque':
        return None
    if resource_kind(storage, getattr(argument, 'type_spec', None)) != 'opaque':
        return None
    if not getattr(argument, 'is_lvalue', False):
        return (
            f'{function_name} consume un descriptor y requiere una variable '
            'lvalue de descriptor opaque'
        )
    state = state_for_value(current_function, argument, namespace)
    display_name = getattr(argument, 'identifier', None) or '<anonimo>'
    if state == CLOSED:
        return f'El descriptor {display_name} esta closed; no puede cerrarse dos veces'
    if state == MOVED:
        return (
            f'El descriptor {display_name} esta moved; su propiedad ya se '
            'transfirio y no puede cerrarse'
        )
    if state != OWNED:
        return (
            f'{function_name} requiere un descriptor owned para consumirlo; '
            f'{display_name} esta en estado {state or "desconocido"}'
        )
    set_state_for_value(current_function, argument, namespace, CLOSED)
    return None


def snapshot(function: object, symbols: Mapping[str, object]) -> dict[object, str]:
    """Capture the states of all visible resource bindings in a path."""
    captured = dict(getattr(function, 'buffer_states', {}))
    for symbol in symbols.values():
        if is_resource_symbol(symbol):
            captured[id(symbol)] = state_for(function, symbol)
        type_spec = getattr(symbol, 'type_spec', None)
        if type_spec is None:
            continue
        for path, _ in _resource_paths(getattr(function, 'scope', None), type_spec):
            captured[_place_key(symbol, path)] = _state_for_resource_path(
                function, symbol, path
            )
    return captured


def restore(function: object, states: Mapping[object, str]) -> None:
    """Restore one path before visiting another control-flow branch."""
    function.buffer_states = dict(states)


def merge(function: object, snapshots: list[Mapping[object, str]]) -> None:
    """Merge paths conservatively without introducing a runtime state.

    A resource consumed on every path keeps that state.  When it is consumed on
    some paths and live on others it becomes ``maybe_*``: a later use is
    invalid, but the diagnostic can say that only some paths consume it.
    ``owned`` and ``borrowed`` only differ for parameters, which cannot become
    owned in the current language, so equal live states are preserved.
    """
    merged: dict[object, str] = {}
    keys = set().union(*(states.keys() for states in snapshots))
    for key in keys:
        values = [states[key] for states in snapshots if key in states]
        consumed = [state for state in values if state in _CONSUMED_STATES]
        partial = [state for state in values if state in _MAYBE_KIND]
        if not consumed and not partial:
            if values:
                merged[key] = values[0]
            continue
        kind = next(
            (state for state in _CONSUMED_STATES if state in consumed), None
        )
        if kind is not None and len(consumed) == len(values):
            merged[key] = kind
            continue
        kind = kind or _MAYBE_KIND[partial[0]]
        merged[key] = _MAYBE_OF[kind]
    restore(function, merged)


def _if_branches(node: object) -> tuple[list[tuple[object, object]], object | None]:
    """Extract ``if``/``elif`` bodies while preserving source order."""
    branches: list[tuple[object, object]] = []
    else_body = None
    if_signature = None

    for child in _children(node):
        name = getattr(child, 'name', None)
        if name == 'IF_SIGNATURE':
            if_signature = child
        elif name == 'STATEMENT_BODY' and if_signature is not None:
            branches.append((if_signature, child))
            if_signature = None
        elif name == 'ELIF':
            signature = next(
                (
                    item for item in _children(child)
                    if getattr(item, 'name', None) == 'ELIF_SIGNATURE'
                ),
                None,
            )
            body = next(
                (
                    item for item in _children(child)
                    if getattr(item, 'name', None) == 'STATEMENT_BODY'
                ),
                None,
            )
            if signature is not None and body is not None:
                branches.append((signature, body))
        elif name == 'ELSE':
            else_body = next(
                (
                    item for item in _children(child)
                    if getattr(item, 'name', None) == 'STATEMENT_BODY'
                ),
                None,
            )

    return branches, else_body


if_branches = _if_branches


def analyze_if(
    function: object,
    node: object,
    symbols: Mapping[str, object],
    visit: Callable[[object], None],
    terminates: Callable[[object], bool] | None = None,
) -> bool:
    """Visit each conditional path and conservatively merge its states.

    ``visit`` performs the regular semantic validation for one AST node.  The
    ownership layer only controls state snapshots; it does not validate
    conditions or emit code.  ``terminates`` reports whether a branch body
    always leaves the flow (``return``, ``break``, ``continue`` or a ``Never``
    call); such a branch never reaches the code after the conditional, so its
    states are excluded from the merge.
    """
    branches, else_body = _if_branches(node)
    if not branches:
        return False

    def reaches_join(body: object) -> bool:
        return terminates is None or not terminates(body)

    baseline = snapshot(function, symbols)
    paths: list[Mapping[int, str]] = []
    for signature, body in branches:
        restore(function, baseline)
        visit(signature)
        visit(body)
        if reaches_join(body):
            paths.append(snapshot(function, symbols))

    if else_body is None:
        # A conditional can be false, so the fall-through path keeps baseline.
        paths.append(baseline)
    else:
        restore(function, baseline)
        visit(else_body)
        if reaches_join(else_body):
            paths.append(snapshot(function, symbols))

    if paths:
        merge(function, paths)
    else:
        # Every path leaves the flow; the code after the conditional is
        # unreachable, so keep the pre-branch states.
        restore(function, baseline)
    return True


def analyze_loop(
    function: object,
    nodes: list[object],
    symbols: Mapping[str, object],
    visit: Callable[[object], None],
) -> list[str]:
    """Visit one loop body and merge it with the zero-iteration path.

    Returns the names of descriptors declared before the loop that the body
    closes or moves: a second iteration would use them after consumption.
    """
    baseline = snapshot(function, symbols)
    for child in nodes:
        visit(child)
    body = snapshot(function, symbols)
    consumed_in_loop = [
        symbol.name
        for symbol in symbols.values()
        if is_opaque_symbol(symbol)
        and baseline.get(id(symbol)) == OWNED
        and body.get(id(symbol)) != OWNED
    ]
    # The loop may execute zero times, but a later use must also be safe after
    # an iteration that made a buffer dead.
    merge(function, [baseline, body])
    return consumed_in_loop


def _resource_paths(
    storage: object | None,
    type_spec: TypeSpec,
    path: tuple[tuple[str, object], ...] = (),
    seen: set[str] | None = None,
) -> list[tuple[tuple[tuple[str, object], ...], str]]:
    kind = resource_kind(storage, type_spec)
    if kind is not None:
        return [(path, kind)]
    resolver = getattr(storage, 'resolve_type', None)
    declared = resolver(type_spec.name) if callable(resolver) else None
    if not isinstance(declared, AggregateSymbol):
        return []
    seen = set() if seen is None else seen
    key = declared.registry_key or declared.name
    if key in seen:
        return []
    seen.add(key)
    paths: list[tuple[tuple[tuple[str, object], ...], str]] = []
    for field in declared.all_fields:
        paths.extend(_resource_paths(
            storage,
            field.type_spec,
            (*path, ('member', field.name)),
            seen.copy(),
        ))
    return paths


def _state_for_resource_path(
    function: object,
    symbol: object,
    path: tuple[tuple[str, object], ...],
) -> str:
    states = getattr(function, 'buffer_states', {})
    for count in range(0, len(path) + 1):
        state = states.get(_place_key(symbol, path[:count]))
        if state in {DEAD, CLOSED, MOVED, MAYBE_DEAD, MAYBE_CLOSED, MAYBE_MOVED}:
            return state
    state = states.get(_place_key(symbol, path))
    if state is not None:
        return state
    initial = initial_state(symbol)
    if initial is not None:
        return initial
    return BORROWED if getattr(symbol, 'scope_kind', None) == 'parameter' else OWNED


def leak_messages(
    function: object,
    symbols: object,
    storage: object | None = None,
) -> list[str]:
    """Describe resources in ``symbols`` that leave scope still owned.

    A buffer or descriptor that is ``owned`` (or ``maybe_*``: consumed only on
    some paths) when its scope ends was never freed or transferred.  Each
    binding is reported once per function, even if several exits leak it.
    """
    reported = getattr(function, 'leak_reported', None)
    name = getattr(function, 'name', None) or '<anonima>'
    messages: list[str] = []
    for symbol in symbols:
        if getattr(symbol, 'scope_kind', None) != 'local':
            continue
        type_spec = getattr(symbol, 'type_spec', None)
        if type_spec is None:
            continue
        for path, kind in _resource_paths(storage, type_spec):
            state = _state_for_resource_path(function, symbol, path)
            if state not in _LEAK_STATES:
                continue
            report_key = (id(symbol), path)
            if reported is not None:
                if report_key in reported:
                    continue
                reported.add(report_key)
            partial = state != OWNED
            where = 'en alguna ruta ' if partial else ''
            place_name = '.'.join(
                (symbol.name, *(str(item) for _, item in path))
            )
            if kind == 'buffer':
                messages.append(
                    f'{name}: el buffer {place_name} sale de su ambito '
                    f'{where}sin Del (fuga de memoria)'
                )
            else:
                messages.append(
                    f'{name}: el descriptor {place_name} sale de su ambito '
                    f'{where}sin cerrarse ni transferirse (fuga de recurso)'
                )
    return messages

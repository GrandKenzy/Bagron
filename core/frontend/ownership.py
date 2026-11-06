"""Compile-time ownership states for buffers and opaque descriptors.

The state is semantic metadata only.  It is never lowered to LLVM, stored in
the buffer descriptor, or represented in the generated ABI.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping


OWNED = 'owned'
BORROWED = 'borrowed'
DEAD = 'dead'
CLOSED = 'closed'
MOVED = 'moved'
BUFFER_STATES = frozenset({OWNED, BORROWED, DEAD})
# NOTA: estados "quizas": el recurso esta consumido en algunas rutas de control
# que confluyen y vivo en otras. Solo nacen de ``merge``.
MAYBE_DEAD = 'maybe_dead'
MAYBE_CLOSED = 'maybe_closed'
MAYBE_MOVED = 'maybe_moved'
RESOURCE_STATES = frozenset({
    OWNED, BORROWED, DEAD, CLOSED, MOVED,
    MAYBE_DEAD, MAYBE_CLOSED, MAYBE_MOVED,
})
# NOTA: estados que ya no pueden usarse; el orden fija cual se informa cuando
# dos rutas de control consumen el recurso de forma distinta.
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
    symbol = (
        namespace(getattr(argument, 'identifier', ''))
        if getattr(argument, 'identifier', None)
        else None
    )
    if not consumes_opaque_arguments(function, function_name):
        return None
    if not is_opaque_symbol(symbol):
        return None
    if (
        type_spec is None
        or getattr(type_spec, 'name', None)
        != getattr(getattr(symbol, 'type_spec', None), 'name', None)
    ):
        return None
    if not getattr(argument, 'is_lvalue', False):
        return (
            f'{function_name} consume un descriptor y requiere una variable '
            'lvalue de descriptor opaque'
        )
    state = state_for(current_function, symbol)
    if state == CLOSED:
        return f'El descriptor {symbol.name} esta closed; no puede cerrarse dos veces'
    if state == MOVED:
        return (
            f'El descriptor {symbol.name} esta moved; su propiedad ya se '
            'transfirio y no puede cerrarse'
        )
    if state != OWNED:
        return (
            f'{function_name} requiere un descriptor owned para consumirlo; '
            f'{symbol.name} esta en estado {state or "desconocido"}'
        )
    set_state(current_function, symbol, CLOSED)
    return None


def transfer_opaque(
    function: object | None,
    target: object | None,
    source: object,
    namespace: Callable[[str], object | None],
) -> str | None:
    """Move an owned opaque descriptor into ``target`` on copy or assignment.

    A descriptor is a unique handle: copying it would leave two owners able to
    close the same resource.  The source becomes ``moved`` and ``target``
    becomes ``owned``.  Values that are not a named binding (for example call
    results) are fresh handles and only make ``target`` owned.
    """
    if not is_opaque_symbol(target):
        return None
    name = getattr(source, 'identifier', None)
    origin = namespace(name) if name else None
    if origin is None or not is_opaque_symbol(origin):
        set_state(function, target, OWNED)
        return None
    if origin is target:
        return None
    if getattr(origin, 'scope_kind', None) == 'global':
        return (
            f'El descriptor global {origin.name} no puede transferirse: su '
            'propiedad no es local a la funcion'
        )
    state = state_for(function, origin)
    if state == BORROWED:
        return (
            f'El descriptor {origin.name} es borrowed; no puede transferirse '
            'a otra variable'
        )
    if state != OWNED:
        return (
            f'El descriptor {origin.name} esta en estado '
            f'{state or "desconocido"}; solo un descriptor owned puede '
            'transferirse'
        )
    set_state(function, origin, MOVED)
    set_state(function, target, OWNED)
    return None


def snapshot(function: object, symbols: Mapping[str, object]) -> dict[int, str]:
    """Capture the states of all visible resource bindings in a path."""
    return {
        id(symbol): state_for(function, symbol)
        for symbol in symbols.values()
        if is_resource_symbol(symbol)
    }


def restore(function: object, states: Mapping[int, str]) -> None:
    """Restore one path before visiting another control-flow branch."""
    function.buffer_states = dict(states)


def merge(function: object, snapshots: list[Mapping[int, str]]) -> None:
    """Merge paths conservatively without introducing a runtime state.

    A resource consumed on every path keeps that state.  When it is consumed on
    some paths and live on others it becomes ``maybe_*``: a later use is
    invalid, but the diagnostic can say that only some paths consume it.
    ``owned`` and ``borrowed`` only differ for parameters, which cannot become
    owned in the current language, so equal live states are preserved.
    """
    merged: dict[int, str] = {}
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


def leak_messages(function: object, symbols: object) -> list[str]:
    """Describe resources in ``symbols`` that leave scope still owned.

    A buffer or descriptor that is ``owned`` (or ``maybe_*``: consumed only on
    some paths) when its scope ends was never freed or transferred.  Each
    binding is reported once per function, even if several exits leak it.
    """
    reported = getattr(function, 'leak_reported', None)
    name = getattr(function, 'name', None) or '<anonima>'
    messages: list[str] = []
    for symbol in symbols:
        if not is_resource_symbol(symbol):
            continue
        if getattr(symbol, 'scope_kind', None) != 'local':
            continue
        if state_for(function, symbol) not in _LEAK_STATES:
            continue
        if reported is not None:
            if id(symbol) in reported:
                continue
            reported.add(id(symbol))
        partial = state_for(function, symbol) != OWNED
        where = 'en alguna ruta ' if partial else ''
        if is_buffer_symbol(symbol):
            messages.append(
                f'{name}: el buffer {symbol.name} sale de su ambito '
                f'{where}sin Del (fuga de memoria)'
            )
        else:
            messages.append(
                f'{name}: el descriptor {symbol.name} sale de su ambito '
                f'{where}sin cerrarse ni transferirse (fuga de recurso)'
            )
    return messages

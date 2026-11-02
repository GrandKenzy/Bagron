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
BUFFER_STATES = frozenset({OWNED, BORROWED, DEAD})
RESOURCE_STATES = frozenset({OWNED, BORROWED, DEAD, CLOSED})


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


def consume_opaque_argument(
    function_name: str,
    parameter: object,
    argument: object,
    namespace: Callable[[str], object | None],
    current_function: object | None,
) -> str | None:
    """Apply the source-level ``close_*`` ownership convention.

    Opaque parameters are borrowed by ordinary calls.  A close operation is
    the one explicit consuming operation available in the current syntax.
    """
    type_spec = getattr(parameter, 'type_spec', None)
    symbol = (
        namespace(getattr(argument, 'identifier', ''))
        if getattr(argument, 'identifier', None)
        else None
    )
    if not function_name.startswith('close_') or not is_opaque_symbol(symbol):
        return None
    if (
        type_spec is None
        or getattr(type_spec, 'name', None)
        != getattr(getattr(symbol, 'type_spec', None), 'name', None)
    ):
        return None
    if not getattr(argument, 'is_lvalue', False):
        return 'close_* requiere una variable lvalue de descriptor opaque'
    state = state_for(current_function, symbol)
    if state == CLOSED:
        return f'El descriptor {symbol.name} esta closed; no puede cerrarse dos veces'
    if state != OWNED:
        return (
            f'close_* requiere un descriptor owned; {symbol.name} esta '
            f'en estado {state or "desconocido"}'
        )
    set_state(current_function, symbol, CLOSED)
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

    ``dead`` wins over a live state: a later use must be valid on every path.
    ``owned`` and ``borrowed`` only differ for parameters, which cannot become
    owned in the current language, so equal live states are preserved.
    """
    merged: dict[int, str] = {}
    keys = set().union(*(states.keys() for states in snapshots))
    for key in keys:
        values = [states[key] for states in snapshots if key in states]
        if CLOSED in values:
            merged[key] = CLOSED
        elif DEAD in values:
            merged[key] = DEAD
        elif values:
            merged[key] = values[0]
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


def analyze_if(
    function: object,
    node: object,
    symbols: Mapping[str, object],
    visit: Callable[[object], None],
) -> bool:
    """Visit each conditional path and conservatively merge its states.

    ``visit`` performs the regular semantic validation for one AST node.  The
    ownership layer only controls state snapshots; it does not validate
    conditions or emit code.
    """
    branches, else_body = _if_branches(node)
    if not branches:
        return False

    baseline = snapshot(function, symbols)
    paths: list[Mapping[int, str]] = []
    for signature, body in branches:
        restore(function, baseline)
        visit(signature)
        visit(body)
        paths.append(snapshot(function, symbols))

    if else_body is None:
        # A conditional can be false, so the fall-through path keeps baseline.
        paths.append(baseline)
    else:
        restore(function, baseline)
        visit(else_body)
        paths.append(snapshot(function, symbols))

    merge(function, paths)
    return True


def analyze_loop(
    function: object,
    nodes: list[object],
    symbols: Mapping[str, object],
    visit: Callable[[object], None],
) -> None:
    """Visit one loop body and merge it with the zero-iteration path."""
    baseline = snapshot(function, symbols)
    for child in nodes:
        visit(child)
    body = snapshot(function, symbols)
    # The loop may execute zero times, but a later use must also be safe after
    # an iteration that made a buffer dead.
    merge(function, [baseline, body])


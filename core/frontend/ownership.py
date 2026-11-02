"""Compile-time ownership states for dynamic buffers.

The state is semantic metadata only.  It is never lowered to LLVM, stored in
the buffer descriptor, or represented in the generated ABI.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping


OWNED = 'owned'
BORROWED = 'borrowed'
DEAD = 'dead'
BUFFER_STATES = frozenset({OWNED, BORROWED, DEAD})


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


def initial_state(symbol: object | None) -> str | None:
    """Get the state before flow analysis: locals own, parameters borrow."""
    if not is_buffer_symbol(symbol):
        return None
    state = getattr(symbol, 'buffer_state', None)
    if state in BUFFER_STATES:
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
    if state not in BUFFER_STATES:
        raise ValueError(f'unknown buffer ownership state: {state}')
    if not is_buffer_symbol(symbol):
        return
    states = getattr(function, 'buffer_states', None)
    if states is None:
        return
    states[id(symbol)] = state


def snapshot(function: object, symbols: Mapping[str, object]) -> dict[int, str]:
    """Capture the states of all visible buffer bindings in a path."""
    return {
        id(symbol): state_for(function, symbol)
        for symbol in symbols.values()
        if is_buffer_symbol(symbol)
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
        if DEAD in values:
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


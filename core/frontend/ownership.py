"""Compile-time ownership states for dynamic buffers.

The state is semantic metadata only.  It is never lowered to LLVM, stored in
the buffer descriptor, or represented in the generated ABI.
"""

from __future__ import annotations

from collections.abc import Mapping


OWNED = 'owned'
BORROWED = 'borrowed'
DEAD = 'dead'
BUFFER_STATES = frozenset({OWNED, BORROWED, DEAD})


def is_buffer_symbol(symbol: object | None) -> bool:
    type_spec = getattr(symbol, 'type_spec', None)
    return bool(
        type_spec is not None
        and getattr(type_spec, 'name', None) == 'buffer'
        and getattr(type_spec, 'pointer_level', 0) == 0
        and getattr(type_spec, 'array_depth', 0) == 0
        and len(getattr(type_spec, 'array_lengths', ())) == 1
    )


def initial_state(symbol: object | None) -> str | None:
    if not is_buffer_symbol(symbol):
        return None
    state = getattr(symbol, 'buffer_state', None)
    if state in BUFFER_STATES:
        return state
    return BORROWED if getattr(symbol, 'scope_kind', None) == 'parameter' else OWNED


def state_for(function: object | None, symbol: object | None) -> str | None:
    initial = initial_state(symbol)
    if initial is None:
        return None
    states = getattr(function, 'buffer_states', None)
    if isinstance(states, Mapping):
        return states.get(id(symbol), initial)
    return initial


def set_state(function: object | None, symbol: object | None, state: str) -> None:
    if state not in BUFFER_STATES:
        raise ValueError(f'unknown buffer ownership state: {state}')
    if not is_buffer_symbol(symbol):
        return
    states = getattr(function, 'buffer_states', None)
    if states is None:
        return
    states[id(symbol)] = state


def snapshot(function: object, symbols: Mapping[str, object]) -> dict[int, str]:
    return {
        id(symbol): state_for(function, symbol)
        for symbol in symbols.values()
        if is_buffer_symbol(symbol)
    }


def restore(function: object, states: Mapping[int, str]) -> None:
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


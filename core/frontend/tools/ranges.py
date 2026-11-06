"""Flow-sensitive proofs for safe indexing of open arrays."""

from __future__ import annotations

from dataclasses import dataclass

from .types.common import UNSIGNED_INTEGER_TYPES
from gram import ast as gast


@dataclass(frozen=True)
class SafeRangeFact:
    """A local proof that an index stays inside an array-compatible range."""

    index: str
    source: str | None
    source_path: tuple[tuple[str, object], ...] = ()
    lower_bound: int = 0
    upper_bound: int | None = None


def _children(node: object) -> list[object]:
    if isinstance(node, list):
        return list(node)
    for attribute in ('nodes', 'items'):
        children = getattr(node, attribute, None)
        if children is not None:
            return list(children)
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


def _bare_identifier(node: object) -> str | None:
    """Return an identifier only when no postfix (such as ``[index]``) exists."""
    if _token_kind(node) == 'IDENT':
        return str(_token_value(node))
    if isinstance(node, gast.ASTRef) and node.name in {
        'ASSIGN_TARGET', 'VALUE', 'POSTFIX_EXPR', 'PRIMARY'
    }:
        children = _children(node)
        if len(children) == 1:
            return _bare_identifier(children[0])
    return None


def _unwrap(node: object) -> object:
    current = node
    while (
        isinstance(current, gast.ASTRef)
        and current.name in {'VALUE', 'POSTFIX_EXPR', 'PRIMARY', 'PAREN_VALUE'}
        and len(current.nodes) == 1
    ):
        current = current.nodes[0]
    return current


def _operator(node: object) -> str | None:
    return getattr(
        getattr(getattr(node, 'operator', None), 'token', None),
        'name',
        None,
    )


def _less_bound(node: object) -> tuple[str, str] | None:
    """Find ``unsigned_index < compiler_length`` in a conjunction."""
    current = _unwrap(node)
    if type(current).__name__ == 'ASTBinaryOp':
        operator = _operator(current)
        if operator == 'LESS':
            left = _identifier(current.left)
            right = _identifier(current.right)
            if left is not None and right is not None:
                return left, right
        if operator in {'AND_LOGIC', 'LOGIC_AND'}:
            return _less_bound(current.left) or _less_bound(current.right)
    return None


def _literal_integer(node: object) -> int | None:
    current = _unwrap(node)
    if _token_kind(current) == 'NUMBER':
        value = _token_value(current)
        return value if isinstance(value, int) else None
    return None


def _less_literal_bound(node: object) -> tuple[str, int] | None:
    """Find ``unsigned_index < integer_literal`` in a condition."""
    current = _unwrap(node)
    if type(current).__name__ == 'ASTBinaryOp':
        operator = _operator(current)
        if operator == 'LESS':
            left = _identifier(current.left)
            right = _literal_integer(current.right)
            if left is not None and right is not None:
                return left, right
        if operator in {'AND_LOGIC', 'LOGIC_AND'}:
            return _less_literal_bound(current.left) or _less_literal_bound(current.right)
    return None


def _array_source_for_length(function: object, length_name: str):
    parameters = getattr(getattr(function, 'signature', None), 'parameters', ())
    parameter = next(
        (
            item for item in parameters
            if getattr(item, 'name', None) == length_name
            and getattr(item, 'is_length', False)
        ),
        None,
    )
    source_name = getattr(parameter, 'length_of', None)
    if source_name is None:
        return None
    source = getattr(function, 'local_variables', {}).get(source_name)
    type_spec = getattr(source, 'type_spec', None)
    if type_spec is None:
        return None
    if (
        type_spec.pointer_level
        or type_spec.array_depth == 0
        or type_spec.name == 'buffer'
    ):
        return None
    return source_name


def fact_from_condition(function: object, condition: object) -> SafeRangeFact | None:
    """Build a fact from a direct ``Len_t`` or literal-bound comparison."""
    bound = _less_bound(condition)
    literal_bound = _less_literal_bound(condition)
    if bound is not None:
        index_name, length_name = bound
        source_name = _array_source_for_length(function, length_name)
        if source_name is None:
            return None
        index = getattr(function, 'local_variables', {}).get(index_name)
        upper_bound = None
    elif literal_bound is not None:
        index_name, upper_bound = literal_bound
        if upper_bound < 0:
            return None
        source_name = None
        index = getattr(function, 'local_variables', {}).get(index_name)
    else:
        return None
    type_spec = getattr(index, 'type_spec', None)
    if type_spec is None or (
        type_spec.pointer_level
        or type_spec.array_depth
        or type_spec.name not in UNSIGNED_INTEGER_TYPES
    ):
        return None
    return SafeRangeFact(
        index_name,
        source_name,
        lower_bound=0,
        upper_bound=upper_bound,
    )


def _walk(node: object):
    yield node
    if type(node).__name__ == 'ASTBinaryOp':
        yield from _walk(node.left)
        yield from _walk(node.right)
        return
    for child in _children(node):
        yield from _walk(child)


def _postfix_suffixes(node: object) -> list[object]:
    children = _children(node)
    suffixes: list[object] = []
    for child in children[1:]:
        suffixes.extend(child if isinstance(child, list) else [child])
    return suffixes


def _is_index_access(node: object, fact: SafeRangeFact) -> bool:
    if not isinstance(node, gast.ASTRef) or node.name != 'POSTFIX_EXPR':
        return False
    children = _children(node)
    if not children:
        return False
    if fact.source is not None and _identifier(children[0]) != fact.source:
        return False
    for suffix in _postfix_suffixes(node):
        if not isinstance(suffix, gast.ASTRef) or suffix.name != 'INDEX_ACCESS':
            continue
        index_node = next(
            (
                child for child in _children(suffix)
                if isinstance(child, gast.ASTRef) and child.name == 'VALUE'
            ),
            None,
        )
        if index_node is not None and _identifier(index_node) == fact.index:
            return True
    return False


def body_preserves_range(body: object, fact: SafeRangeFact) -> bool:
    """Allow index updates only after the last proven access in the body."""
    events: list[tuple[str, int]] = []
    for position, node in enumerate(_walk(body)):
        if _is_index_access(node, fact):
            events.append(('access', position))
        if isinstance(node, gast.ASTRef) and node.name == 'VAR_ASSIGNATION':
            target = next(
                (
                    child for child in _children(node)
                    if isinstance(child, gast.ASTRef)
                    and child.name == 'ASSIGN_TARGET'
                ),
                None,
            )
            target_name = _bare_identifier(target) if target is not None else None
            if target_name == fact.index:
                events.append(('write', position))
            elif target_name == fact.source and _bare_identifier(target) is not None:
                # Rebinding an array invalidates the provenance used by the fact.
                events.append(('source_write', position))

    if any(kind == 'source_write' for kind, _ in events):
        return False
    accesses = [position for kind, position in events if kind == 'access']
    writes = [position for kind, position in events if kind == 'write']
    if not accesses:
        return True
    return not writes or min(writes) > max(accesses)


def for_fact(iterator: object) -> SafeRangeFact | None:
    source = getattr(iterator, 'for_array_source', None)
    if source is None:
        upper_bound = getattr(iterator, 'for_range_upper_bound', None)
        if upper_bound is None:
            return None
        return SafeRangeFact(
            str(getattr(iterator, 'name', '')),
            None,
            lower_bound=getattr(iterator, 'for_range_lower_bound', 0),
            upper_bound=upper_bound,
        )
    return SafeRangeFact(
        str(getattr(iterator, 'name', '')),
        str(source),
        getattr(iterator, 'for_array_path', ()),
        upper_bound=getattr(iterator, 'for_array_length', None),
    )


__all__ = [
    'SafeRangeFact',
    'body_preserves_range',
    'fact_from_condition',
    'for_fact',
]

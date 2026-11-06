"""Flow analysis for fixed arrays and conservative call contracts.

This module deliberately proves less than the language guarantees.  A fixed
local array starts as zeroed storage in Bagron, so an optimization may only
remove that initialization after this analysis proves that every element is
written before the function can observe the array.  Unknown indices, calls,
pointer escapes, and loops without a statically complete write remain
conservative failures.

Private source functions also receive a small summary for fixed-array
parameters.  A caller may treat a parameter as scratch storage only when the
callee writes every element before reading or escaping it, and leaves every
element written on return.  External, public, assembler, and ambiguous calls
remain observable escapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from gram import ast as gast


def _children(node: object) -> list[object]:
    if isinstance(node, list):
        raw = list(node)
    elif type(node).__name__ == 'ASTBinaryOp':
        return [node.left, node.right]
    elif type(node).__name__ == 'ASTUnaryOp':
        return [node.operand]
    else:
        items = getattr(node, 'items', None)
        raw = list(items) if items is not None else list(
            getattr(node, 'nodes', None) or ()
        )
    children: list[object] = []
    for child in raw:
        if isinstance(child, list):
            children.extend(_children(child))
        else:
            children.append(child)
    return children


def _token(node: object) -> object | None:
    return getattr(node, 'token', None)


def _token_kind(node: object) -> str | None:
    token = _token(node)
    token = getattr(token, 'token', token)
    return getattr(token, 'name', None)


def _token_value(node: object) -> object | None:
    token = _token(node)
    return getattr(token, 'value', None)


def _identifier(node: object) -> str | None:
    if _token_kind(node) == 'IDENT':
        return str(_token_value(node))
    for child in _children(node):
        found = _identifier(child)
        if found is not None:
            return found
    return None


def _constant_int(node: object) -> int | None:
    if _token_kind(node) == 'NUMBER':
        value = _token_value(node)
        return value if isinstance(value, int) else None
    # Unwrap the parser's VALUE -> POSTFIX_EXPR -> PRIMARY path, but never
    # search through a compound expression: finding the ``15`` inside
    # ``i - 15`` would turn a dynamic index into a false constant proof.
    children = _children(node)
    if len(children) == 1:
        return _constant_int(children[0])
    return None


def _array_length(variable: object) -> int | None:
    type_spec = getattr(variable, 'type_spec', None)
    if type_spec is None or getattr(type_spec, 'array_depth', 0) != 1:
        return None
    lengths = getattr(type_spec, 'array_lengths', ())
    if len(lengths) != 1 or not isinstance(lengths[0], int):
        return None
    return lengths[0] if lengths[0] > 0 else None


def _array_length_from_type(type_spec: object) -> int | None:
    if getattr(type_spec, 'pointer_level', 0):
        return None
    if getattr(type_spec, 'array_depth', 0) != 1:
        return None
    lengths = getattr(type_spec, 'array_lengths', ())
    if len(lengths) != 1 or not isinstance(lengths[0], int):
        return None
    return lengths[0] if lengths[0] > 0 else None


def _fixed_local_arrays(
    local_variables: Mapping[str, object],
) -> dict[str, int]:
    return {
        name: length
        for name, variable in local_variables.items()
        if getattr(variable, 'scope_kind', None) == 'local'
        and (length := _array_length(variable)) is not None
    }


def _fixed_array_parameters(symbol: object) -> dict[str, int]:
    signature = getattr(symbol, 'signature', None)
    return {
        parameter.name: length
        for parameter in getattr(signature, 'parameters', ())
        if not getattr(parameter, 'is_compiler_supplied', False)
        and (length := _array_length_from_type(
            getattr(parameter, 'type_spec', None)
        )) is not None
    }


@dataclass(frozen=True)
class FixedArrayParameterSummary:
    """Observable contract for one fixed-array parameter.

    ``requires_initialized`` means that some read, compound update, or
    unknown escape can happen before all elements are overwritten.  The
    second field is intentionally independent: a helper may read an input and
    still overwrite the full array before returning.
    """

    requires_initialized: bool
    fully_written_on_return: bool


@dataclass
class _Flow:
    written: dict[str, set[int]]
    invalid: set[str] = field(default_factory=set)
    normal: bool = True

    def copy(self) -> '_Flow':
        return _Flow(
            {name: set(indices) for name, indices in self.written.items()},
            set(self.invalid),
            self.normal,
        )


@dataclass(frozen=True)
class _Target:
    name: str
    indexed: bool
    indices: set[int] | None


class _FixedArrayWriteAnalysis:
    """Conservative forward analysis for one function body."""

    _MAX_TRACKED_RANGE = 4096

    def __init__(
        self,
        arrays: dict[str, int],
        *,
        call_targets: Mapping[int, object] | None = None,
        function_summaries: Mapping[int, Mapping[str, FixedArrayParameterSummary]]
        | None = None,
    ):
        self.arrays = arrays
        self.call_targets = call_targets or {}
        self.function_summaries = function_summaries or {}
        # The active loop context is used only to prove a recurrence such as
        # ``schedule[i - 16]`` after the loop has written ``schedule[i]``.
        # It is deliberately narrower than general range reasoning.
        self._active_loop: tuple[str, int, int, int] | None = None
        self._active_loop_writes: set[str] = set()

    def run(self, body: object) -> set[str]:
        initial = _Flow({name: set() for name in self.arrays})
        result = self._sequence(_children(body), initial, {})
        if not result.normal:
            return set()
        return {
            name
            for name, capacity in self.arrays.items()
            if name not in result.invalid
            and result.written[name] == set(range(capacity))
        }

    def run_summary(
        self,
        body: object,
    ) -> dict[str, FixedArrayParameterSummary]:
        """Summarize fixed-array parameters from an uninitialized entry state."""
        initial = _Flow({name: set() for name in self.arrays})
        result = self._sequence(_children(body), initial, {})
        return {
            name: FixedArrayParameterSummary(
                requires_initialized=name in result.invalid,
                fully_written_on_return=(
                    result.normal
                    and name not in result.invalid
                    and result.written[name] == set(range(capacity))
                ),
            )
            for name, capacity in self.arrays.items()
        }

    def _sequence(
        self,
        nodes: list[object],
        flow: _Flow,
        loop_domains: dict[str, set[int]],
    ) -> _Flow:
        current = flow
        for node in nodes:
            if not current.normal:
                break
            current = self._node(node, current, loop_domains)
        return current

    def _node(
        self,
        node: object,
        flow: _Flow,
        loop_domains: dict[str, set[int]],
    ) -> _Flow:
        if not isinstance(node, gast.ASTRef):
            return flow

        if node.name in {'FUNCTION_BODY', 'STATEMENT_BODY'}:
            return self._sequence(_children(node), flow, loop_domains)
        if node.name == 'VAR':
            return self._variable(node, flow, loop_domains)
        if node.name == 'VAR_ASSIGNATION':
            return self._assignment(node, flow, loop_domains)
        if node.name == 'IF':
            return self._if(node, flow, loop_domains)
        if node.name == 'FOR':
            return self._for(node, flow, loop_domains)
        if node.name == 'WHILE':
            return self._while(node, flow, loop_domains)
        if node.name in {'RETURN', 'RETURN_ASM'}:
            for child in _children(node):
                if getattr(child, 'name', None) == 'VALUE':
                    self._expression(child, flow, loop_domains)
            return flow

        self._expression(node, flow, loop_domains)
        return flow

    def _variable(
        self,
        node: gast.ASTRef,
        flow: _Flow,
        loop_domains: dict[str, set[int]],
    ) -> _Flow:
        declaration = next(
            (
                child for child in _children(node)
                if getattr(child, 'name', None)
                in {'VAR_DECLARATION', 'VAR_INITIALIZATION'}
            ),
            None,
        )
        if declaration is None:
            return flow
        name = _identifier(declaration)
        declaration_children = _children(declaration)
        assign_position = next(
            (
                index for index, child in enumerate(declaration_children)
                if _token_kind(child) == 'ASSIGN'
            ),
            None,
        )
        value = (
            next(
                (
                    child for child in declaration_children[assign_position + 1:]
                    if getattr(child, 'name', None) == 'VALUE'
                ),
                None,
            )
            if assign_position is not None
            else None
        )
        if value is not None:
            self._expression(value, flow, loop_domains)
            if name in self.arrays:
                flow.written[name] = set(range(self.arrays[name]))
        return flow

    def _assignment(
        self,
        node: gast.ASTRef,
        flow: _Flow,
        loop_domains: dict[str, set[int]],
    ) -> _Flow:
        target = next(
            (
                child for child in _children(node)
                if getattr(child, 'name', None) == 'ASSIGN_TARGET'
            ),
            None,
        )
        operator = next(
            (
                _token_value(child) for child in _children(node)
                if _token_kind(child) in {
                    'ASSIGN', 'PLUS_ASSIGN', 'MINUS_ASSIGN',
                    'STAR_ASSIGN', 'SLASH_ASSIGN', 'PERCENT_ASSIGN',
                    'AND_ASSIGN', 'OR_ASSIGN', 'XOR_ASSIGN',
                    'SHL_ASSIGN', 'SHR_ASSIGN',
                }
            ),
            '=',
        )
        value = next(
            (
                child for child in _children(node)
                if getattr(child, 'name', None) == 'VALUE'
            ),
            None,
        )
        if value is not None:
            self._expression(value, flow, loop_domains)
        target_info = self._target(target, flow, loop_domains)
        if target_info is None:
            return flow
        name = target_info.name
        indices = target_info.indices
        if target_info.indexed and indices is None:
            if operator != '=':
                self._require_all(flow, name)
            return flow
        if operator != '=':
            self._require_indices(flow, name, indices)
        if not target_info.indexed:
            flow.written[name] = set(range(self.arrays[name]))
        else:
            assert indices is not None
            flow.written[name].update(indices)
        return flow

    def _target(
        self,
        target: object | None,
        flow: _Flow,
        loop_domains: dict[str, set[int]],
    ) -> _Target | None:
        if target is None:
            return None
        postfix = next(
            (
                child for child in _children(target)
                if getattr(child, 'name', None) == 'POSTFIX_EXPR'
            ),
            None,
        )
        if postfix is None:
            name = _identifier(target)
            return (
                _Target(name, indexed=False, indices=None)
                if name in self.arrays else None
            )
        children = _children(postfix)
        if not children:
            return None
        name = _identifier(children[0])
        if name not in self.arrays:
            return None
        index_suffix = next(
            (
                child for child in children[1:]
                if getattr(child, 'name', None) == 'INDEX_ACCESS'
            ),
            None,
        )
        if index_suffix is None:
            return _Target(name, indexed=False, indices=None)
        index_value = next(
            (
                child for child in _children(index_suffix)
                if getattr(child, 'name', None) == 'VALUE'
            ),
            None,
        )
        if index_value is not None:
            self._expression(index_value, flow, loop_domains)
        return _Target(
            name,
            indexed=True,
            indices=self._index_domain(index_value, loop_domains),
        )

    def _call_arguments(self, call_suffix: object) -> list[object]:
        arguments = next(
            (
                child for child in _children(call_suffix)
                if getattr(child, 'name', None) == 'ARGUMENTS'
            ),
            None,
        )
        if arguments is None:
            return []
        container = next(iter(_children(arguments)), None)
        return _children(container) if container is not None else []

    def _visible_parameters(self, target: object) -> list[object]:
        signature = getattr(target, 'signature', None)
        return [
            parameter
            for parameter in getattr(signature, 'parameters', ())
            if not (
                getattr(parameter, 'is_length', False)
                or getattr(parameter, 'is_size', False)
                or getattr(parameter, 'is_signed', False)
                or getattr(parameter, 'is_region', False)
                or getattr(parameter, 'is_receiver', False)
            )
        ]

    def _whole_array_name(self, argument: object) -> str | None:
        """Return a direct array argument, excluding indexed expressions."""
        current = argument
        while getattr(current, 'name', None) in {'VALUE', 'PAREN_VALUE'}:
            children = _children(current)
            if len(children) != 1:
                return None
            current = children[0]
        if getattr(current, 'name', None) != 'POSTFIX_EXPR':
            return None
        children = _children(current)
        if len(children) != 1:
            return None
        return _identifier(children[0])

    def _direct_identifier(self, node: object) -> str | None:
        """Return an identifier only when the expression has no operators."""
        current = node
        while getattr(current, 'name', None) == 'VALUE':
            children = _children(current)
            if len(children) != 1:
                return None
            current = children[0]
        if getattr(current, 'name', None) != 'POSTFIX_EXPR':
            return None
        children = _children(current)
        if len(children) != 1:
            return None
        return _identifier(children[0])

    def _relative_index_offset(self, node: object) -> int | None:
        """Read ``iterator +/- constant`` without folding dynamic operands."""
        current = node
        while getattr(current, 'name', None) == 'VALUE':
            children = _children(current)
            if len(children) != 1:
                return None
            current = children[0]
        if type(current).__name__ != 'ASTBinaryOp':
            return None
        operator = getattr(
            getattr(getattr(current, 'operator', None), 'token', None),
            'name',
            None,
        )
        iterator = self._active_loop[0] if self._active_loop is not None else None
        left_name = self._direct_identifier(current.left)
        right_value = _constant_int(current.right)
        if left_name == iterator and right_value is not None:
            return right_value if operator == 'PLUS' else -right_value if operator == 'MINUS' else None
        right_name = self._direct_identifier(current.right)
        left_value = _constant_int(current.left)
        if right_name == iterator and left_value is not None:
            return left_value if operator == 'PLUS' else None
        return None

    def _relative_index_is_prior(
        self,
        name: str,
        index: object,
        flow: _Flow,
    ) -> bool:
        """Prove a loop-relative read observes an earlier loop write."""
        loop = self._active_loop
        if loop is None or name not in self._active_loop_writes:
            return False
        iterator, start, stop, step = loop
        offset = self._relative_index_offset(index)
        if offset is None or offset >= 0 or step != 1:
            return False
        capacity = self.arrays[name]
        first_index = start + offset
        last_index = (stop - 1) + offset
        if first_index < 0 or last_index >= capacity:
            return False
        # Every element before the loop start must already be initialized;
        # subsequent indices are written by prior iterations of i.
        return set(range(0, start)).issubset(flow.written[name])

    def _call_effect(
        self,
        node: object,
        call_suffix: object,
        flow: _Flow,
        loop_domains: dict[str, set[int]],
    ) -> None:
        """Apply a private callee's fixed-array contract at one call site."""
        arguments = self._call_arguments(call_suffix)
        target = self.call_targets.get(id(node))
        summaries = self.function_summaries.get(id(target)) if target else None
        analyzable = bool(
            target is not None
            and getattr(target, 'privacy', 'public') == 'private'
            and not getattr(target, 'is_external', False)
            and not getattr(target, 'is_assembler', False)
            and not getattr(target, 'is_compiled', False)
            and summaries is not None
        )
        if not analyzable:
            for argument in arguments:
                self._expression(argument, flow, loop_domains)
            return

        parameters = self._visible_parameters(target)
        for parameter, argument in zip(parameters, arguments):
            parameter_length = _array_length_from_type(
                getattr(parameter, 'type_spec', None)
            )
            argument_name = self._whole_array_name(argument)
            summary = summaries.get(getattr(parameter, 'name', ''))
            if (
                parameter_length is not None
                and argument_name in self.arrays
                and summary is not None
            ):
                if summary.requires_initialized:
                    self._require_all(flow, argument_name)
                if summary.fully_written_on_return:
                    flow.written[argument_name] = set(
                        range(self.arrays[argument_name])
                    )
                continue
            self._expression(argument, flow, loop_domains)

        # A malformed or future call shape must not make this optimization
        # optimistic.  Semantic validation normally catches the mismatch;
        # this guard protects the standalone analysis from changing that rule.
        for argument in arguments[len(parameters):]:
            self._expression(argument, flow, loop_domains)

    def _expression(
        self,
        node: object,
        flow: _Flow,
        loop_domains: dict[str, set[int]],
    ) -> None:
        if not isinstance(node, gast.ASTRef):
            return
        if node.name == 'CALL':
            call_suffix = next(
                (
                    child for child in _children(node)
                    if getattr(child, 'name', None) == 'CALL_SUFFIX'
                ),
                None,
            )
            if call_suffix is not None:
                self._call_effect(node, call_suffix, flow, loop_domains)
            return
        if node.name == 'POSTFIX_EXPR':
            children = _children(node)
            if not children:
                return
            call_suffix = next(
                (
                    child for child in children[1:]
                    if getattr(child, 'name', None) == 'CALL_SUFFIX'
                ),
                None,
            )
            if call_suffix is not None:
                self._call_effect(node, call_suffix, flow, loop_domains)
                return
            base_name = _identifier(children[0])
            index_suffix = next(
                (
                    child for child in children[1:]
                    if getattr(child, 'name', None) == 'INDEX_ACCESS'
                ),
                None,
            )
            if base_name in self.arrays and index_suffix is not None:
                index_value = next(
                    (
                        child for child in _children(index_suffix)
                        if getattr(child, 'name', None) == 'VALUE'
                    ),
                    None,
                )
                if index_value is not None:
                    self._expression(index_value, flow, loop_domains)
                indices = self._index_domain(index_value, loop_domains)
                if not (
                    indices is None
                    and self._relative_index_is_prior(
                        base_name,
                        index_value,
                        flow,
                    )
                ):
                    self._require_indices(flow, base_name, indices)
                for child in children[1:]:
                    if child is not index_suffix:
                        self._expression(child, flow, loop_domains)
                return
            if base_name in self.arrays:
                self._require_all(flow, base_name)
                return
        if node.name == 'PRIMARY':
            name = _identifier(node)
            if name in self.arrays:
                self._require_all(flow, name)
                return
        for child in _children(node):
            self._expression(child, flow, loop_domains)

    def _index_domain(
        self,
        node: object | None,
        loop_domains: dict[str, set[int]],
    ) -> set[int] | None:
        if node is None:
            return None
        constant = _constant_int(node)
        if constant is not None:
            return {constant}
        name = _identifier(node)
        return set(loop_domains[name]) if name in loop_domains else None

    def _require_all(self, flow: _Flow, name: str) -> None:
        if flow.written[name] != set(range(self.arrays[name])):
            flow.invalid.add(name)

    def _require_indices(
        self,
        flow: _Flow,
        name: str,
        indices: set[int] | None,
    ) -> None:
        if indices is None:
            self._require_all(flow, name)
            return
        if any(
            index < 0
            or index >= self.arrays[name]
            or index not in flow.written[name]
            for index in indices
        ):
            flow.invalid.add(name)

    def _if(
        self,
        node: gast.ASTRef,
        flow: _Flow,
        loop_domains: dict[str, set[int]],
    ) -> _Flow:
        branches: list[object] = []
        else_body = None
        pending_if = False
        for child in _children(node):
            name = getattr(child, 'name', None)
            if name == 'IF_SIGNATURE':
                self._expression(child, flow, loop_domains)
                pending_if = True
            elif name == 'STATEMENT_BODY' and pending_if:
                branches.append(child)
                pending_if = False
            elif name in {'ELIF', 'ELSE'}:
                signature = next(
                    (
                        item for item in _children(child)
                        if getattr(item, 'name', None)
                        in {'ELIF_SIGNATURE', 'ELSE_SIGNATURE'}
                    ),
                    None,
                )
                if signature is not None:
                    self._expression(signature, flow, loop_domains)
                body = next(
                    (
                        item for item in _children(child)
                        if getattr(item, 'name', None) == 'STATEMENT_BODY'
                    ),
                    None,
                )
                if name == 'ELSE':
                    else_body = body
                elif body is not None:
                    branches.append(body)
        paths = [self._sequence(_children(body), flow.copy(), loop_domains) for body in branches]
        if else_body is not None:
            paths.append(
                self._sequence(_children(else_body), flow.copy(), loop_domains)
            )
        else:
            paths.append(flow.copy())
        return self._merge(paths)

    def _while(
        self,
        node: gast.ASTRef,
        flow: _Flow,
        loop_domains: dict[str, set[int]],
    ) -> _Flow:
        signature = next(
            (
                child for child in _children(node)
                if getattr(child, 'name', None) == 'WHILE_SIGNATURE'
            ),
            None,
        )
        if signature is not None:
            self._expression(signature, flow, loop_domains)
        body = next(
            (
                child for child in _children(node)
                if getattr(child, 'name', None) == 'STATEMENT_BODY'
            ),
            None,
        )
        if body is not None:
            self._sequence(_children(body), flow.copy(), loop_domains)
        # A while loop may execute zero times, so no body write is definite.
        return flow

    def _loop_writes_iterator(
        self,
        nodes: list[object],
        iterator: str,
    ) -> set[str]:
        """Find arrays assigned at the current numeric-loop iterator."""
        result: set[str] = set()
        for node in nodes:
            if not isinstance(node, gast.ASTRef):
                continue
            if node.name == 'VAR_ASSIGNATION':
                target = next(
                    (
                        child for child in _children(node)
                        if getattr(child, 'name', None) == 'ASSIGN_TARGET'
                    ),
                    None,
                )
                postfix = next(
                    (
                        child for child in _children(target)
                        if getattr(child, 'name', None) == 'POSTFIX_EXPR'
                    ),
                    None,
                ) if target is not None else None
                if postfix is None:
                    continue
                children = _children(postfix)
                if len(children) != 2:
                    continue
                index_suffix = next(
                    (
                        child for child in children[1:]
                        if getattr(child, 'name', None) == 'INDEX_ACCESS'
                    ),
                    None,
                )
                index_value = next(
                    (
                        child for child in _children(index_suffix)
                        if getattr(child, 'name', None) == 'VALUE'
                    ),
                    None,
                ) if index_suffix is not None else None
                if self._direct_identifier(index_value) != iterator:
                    continue
                name = _identifier(children[0])
                if name in self.arrays:
                    result.add(name)
                continue
            if node.name in {'IF', 'STATEMENT_BODY'}:
                result.update(
                    self._loop_writes_iterator(_children(node), iterator)
                )
        return result

    def _for(
        self,
        node: gast.ASTRef,
        flow: _Flow,
        loop_domains: dict[str, set[int]],
    ) -> _Flow:
        signature = next(
            (
                child for child in _children(node)
                if getattr(child, 'name', None) == 'FOR_SIGNATURE'
            ),
            None,
        )
        body = next(
            (
                child for child in _children(node)
                if getattr(child, 'name', None) == 'STATEMENT_BODY'
            ),
            None,
        )
        if signature is None or body is None:
            return flow
        values = [
            child for child in _children(signature)
            if getattr(child, 'name', None) == 'VALUE'
        ]
        iterator = _identifier(signature)
        if len(values) != 3 or iterator is None:
            self._sequence(_children(body), flow.copy(), loop_domains)
            return flow
        start = _constant_int(values[0])
        stop = _constant_int(values[1])
        step = _constant_int(values[2])
        if start is None or stop is None or step in {None, 0}:
            self._sequence(_children(body), flow.copy(), loop_domains)
            return flow
        domain = set(range(start, stop, step))
        if len(domain) > self._MAX_TRACKED_RANGE:
            self._sequence(_children(body), flow.copy(), loop_domains)
            return flow
        child_domains = dict(loop_domains)
        child_domains[iterator] = domain
        # Do not use the loop iterator's whole domain as a write fact while
        # analyzing one body execution.  That would incorrectly prove a read
        # after ``data[i] = value`` for another index in the same iteration.
        previous_loop = self._active_loop
        previous_writes = self._active_loop_writes
        self._active_loop = (iterator, start, stop, step)
        self._active_loop_writes = self._loop_writes_iterator(
            _children(body), iterator
        )
        try:
            body_flow = self._sequence(
                _children(body), flow.copy(), loop_domains
            )
        finally:
            self._active_loop = previous_loop
            self._active_loop_writes = previous_writes
        flow.invalid.update(body_flow.invalid)
        if not domain:
            return flow
        # A loop body is one execution path.  Only propagate writes that are
        # known to use the loop iterator as a complete finite index domain.
        writes = self._guaranteed_writes(
            _children(body), flow.copy(), child_domains
        )
        for name, indices in writes.items():
            combined = flow.written[name] | indices
            if all(
                0 <= index < self.arrays[name] for index in indices
            ):
                # Preserve partial coverage as well as complete coverage.  A
                # later loop may use this prefix as the entry state for a
                # recurrence such as schedule[i - 16].
                flow.written[name] = combined
        return flow

    def _guaranteed_writes(
        self,
        nodes: list[object],
        flow: _Flow,
        loop_domains: dict[str, set[int]],
    ) -> dict[str, set[int]]:
        result = {name: set() for name in self.arrays}
        for node in nodes:
            if not isinstance(node, gast.ASTRef):
                continue
            if node.name == 'VAR_ASSIGNATION':
                target = next(
                    (
                        child for child in _children(node)
                        if getattr(child, 'name', None) == 'ASSIGN_TARGET'
                    ),
                    None,
                )
                target_info = self._target(target, flow, loop_domains)
                if target_info is not None:
                    name = target_info.name
                    indices = target_info.indices
                    if not target_info.indexed:
                        result[name] = set(range(self.arrays[name]))
                    elif indices is not None:
                        result[name].update(indices)
            elif node.name == 'IF':
                branches: list[object] = []
                else_body = None
                pending_if = False
                for child in _children(node):
                    child_name = getattr(child, 'name', None)
                    if child_name == 'IF_SIGNATURE':
                        pending_if = True
                    elif child_name == 'STATEMENT_BODY' and pending_if:
                        branches.append(child)
                        pending_if = False
                    elif child_name in {'ELIF', 'ELSE'}:
                        body = next(
                            (
                                item for item in _children(child)
                                if getattr(item, 'name', None)
                                == 'STATEMENT_BODY'
                            ),
                            None,
                        )
                        if child_name == 'ELSE':
                            else_body = body
                        elif body is not None:
                            branches.append(body)
                if branches and else_body is not None:
                    branch_results = [
                        self._guaranteed_writes(
                            _children(body), flow.copy(), loop_domains
                        )
                        for body in (*branches, else_body)
                    ]
                    for name in self.arrays:
                        result[name] = set.intersection(
                            *(entry[name] for entry in branch_results)
                        )
            elif node.name in {'FOR', 'WHILE'}:
                continue
        return result

    def _merge(self, paths: list[_Flow]) -> _Flow:
        normal_paths = [path for path in paths if path.normal]
        invalid = set().union(*(path.invalid for path in paths))
        if not normal_paths:
            return _Flow(
                {name: set() for name in self.arrays},
                invalid,
                normal=False,
            )
        written = {
            name: set.intersection(
                *(path.written[name] for path in normal_paths)
            )
            for name in self.arrays
        }
        return _Flow(written, invalid, normal=True)


def analyze_fixed_array_writes(
    body: object,
    local_variables: Mapping[str, object],
    *,
    call_targets: Mapping[int, object] | None = None,
    function_summaries: Mapping[
        int, Mapping[str, FixedArrayParameterSummary]
    ] | None = None,
) -> set[str]:
    """Return fixed local arrays definitely written before function exit.

    The result is metadata only.  One-dimensional fixed arrays are analyzed;
    other shapes remain outside the proof until their element model is
    available.
    """
    arrays = _fixed_local_arrays(local_variables)
    if not arrays:
        return set()
    return _FixedArrayWriteAnalysis(
        arrays,
        call_targets=call_targets,
        function_summaries=function_summaries,
    ).run(body)


def summarize_fixed_array_parameters(
    symbol: object,
    *,
    function_summaries: Mapping[
        int, Mapping[str, FixedArrayParameterSummary]
    ] | None = None,
) -> dict[str, FixedArrayParameterSummary]:
    """Summarize fixed-array parameters for one source function."""
    arrays = _fixed_array_parameters(symbol)
    body = getattr(symbol, 'body_node', None)
    if not arrays or body is None:
        return {}
    return _FixedArrayWriteAnalysis(
        arrays,
        call_targets=getattr(symbol, 'call_targets', None),
        function_summaries=function_summaries,
    ).run_summary(body)


def refresh_fixed_array_analysis(symbols: object) -> None:
    """Refresh callee summaries and caller proofs after all bodies resolve.

    Semantic calls can target a function declared later in the source, so the
    per-function metadata collected during body validation is only provisional.
    A small fixed-point pass makes private helper chains usable while keeping
    recursive or ambiguous contracts conservative.
    """
    symbols = [
        symbol for symbol in symbols
        if getattr(symbol, 'body_node', None) is not None
        and not getattr(symbol, 'is_external', False)
    ]
    summaries: dict[
        int, dict[str, FixedArrayParameterSummary]
    ] = {}
    for _ in range(max(1, len(symbols))):
        updated = {
            id(symbol): summarize_fixed_array_parameters(
                symbol,
                function_summaries=summaries,
            )
            for symbol in symbols
        }
        if updated == summaries:
            break
        summaries = updated

    for symbol in symbols:
        symbol.fixed_array_parameter_summary = summaries.get(id(symbol), {})
        symbol.definite_array_writes = analyze_fixed_array_writes(
            getattr(symbol, 'body_node', None),
            getattr(symbol, 'local_variables', {}),
            call_targets=getattr(symbol, 'call_targets', None),
            function_summaries=summaries,
        )


__all__ = [
    'FixedArrayParameterSummary',
    'analyze_fixed_array_writes',
    'refresh_fixed_array_analysis',
    'summarize_fixed_array_parameters',
]

"""Derive LLVM-only parameters from source-level function signatures."""

from __future__ import annotations

from dataclasses import dataclass

from core.frontend.objects import TypeSpec


@dataclass(frozen=True)
class AbiParameter:
    """One runtime parameter, including compiler-generated metadata."""

    name: str
    type_spec: TypeSpec
    source_name: str
    kind: str = 'value'
    is_unique: bool = False
    is_receiver: bool = False

    @property
    def is_length(self) -> bool:
        return self.kind == 'length'

    @property
    def length_of(self) -> str | None:
        return self.source_name if self.is_length else None


@dataclass(frozen=True)
class AbiMetadataPlan:
    """Ordered runtime signature derived from one semantic function."""

    parameters: tuple[AbiParameter, ...]


def _needs_runtime_length(
    type_spec: TypeSpec,
    parameter_name: str,
    chain_lengths: set[str] | None,
) -> bool:
    if type_spec.pointer_level:
        return False
    if type_spec.name == 'chain' and type_spec.array_depth == 0:
        return chain_lengths is None or parameter_name in chain_lengths
    return bool(
        type_spec.array_depth
        and type_spec.array_lengths
        and type_spec.array_lengths[0] is None
    )


def build_abi_metadata_plan(
    symbol: object,
    pointer_size: int,
    chain_lengths: set[str] | None = None,
) -> AbiMetadataPlan:
    """Build runtime parameters without changing the source signature."""

    usize = TypeSpec('usize', bit_width=pointer_size * 8, signed=False)
    runtime: list[AbiParameter] = []
    for parameter in getattr(getattr(symbol, 'signature', None), 'parameters', ()):
        runtime.append(AbiParameter(
            parameter.name,
            parameter.type_spec,
            parameter.name,
            is_unique=parameter.is_unique,
            is_receiver=parameter.is_receiver,
        ))
        if _needs_runtime_length(parameter.type_spec, parameter.name, chain_lengths):
            runtime.append(AbiParameter(
                f'__bg_len_{parameter.name}',
                usize,
                parameter.name,
                kind='length',
            ))
    plan = AbiMetadataPlan(tuple(runtime))
    symbol.abi_metadata_plan = plan
    return plan


def runtime_parameters(symbol: object, pointer_size: int) -> tuple[AbiParameter, ...]:
    """Return the stable runtime parameter sequence for ``symbol``."""

    plan = getattr(symbol, 'abi_metadata_plan', None)
    if not isinstance(plan, AbiMetadataPlan):
        plan = build_abi_metadata_plan(symbol, pointer_size)
    return plan.parameters


def _children(node: object) -> list[object]:
    if isinstance(node, list):
        return list(node)
    items = getattr(node, 'items', None)
    if items is not None:
        return list(items)
    nodes = getattr(node, 'nodes', None)
    return list(nodes) if nodes is not None else []


def _call_arguments(node: object) -> list[object]:
    direct_children = [
        nested
        for child in _children(node)
        for nested in (child if isinstance(child, list) else [child])
    ]
    call = next(
        (child for child in direct_children
         if getattr(child, 'name', None) == 'CALL_SUFFIX'),
        None,
    )
    if call is None:
        return []
    arguments = next(
        (child for child in _children(call)
         if getattr(child, 'name', None) == 'ARGUMENTS'),
        None,
    )
    container = next(iter(_children(arguments)), None) if arguments else None
    return _children(container)


def _identifier(node: object) -> str | None:
    current = node
    while getattr(current, 'name', None) in {'VALUE', 'POSTFIX_EXPR', 'PRIMARY'}:
        children = _children(current)
        if not children:
            return None
        current = children[0]
    token = getattr(current, 'token', None)
    kind = getattr(getattr(token, 'token', None), 'name', None)
    value = getattr(token, 'value', None)
    return str(value) if kind == 'IDENT' and value is not None else None


def _chain_parameters(symbol: object) -> set[str]:
    return {
        parameter.name
        for parameter in getattr(getattr(symbol, 'signature', None), 'parameters', ())
        if (
            parameter.type_spec.name == 'chain'
            and not parameter.type_spec.pointer_level
            and not parameter.type_spec.array_depth
        )
    }


def _walk(node: object):
    yield node
    for child in _children(node):
        yield from _walk(child)


def build_abi_metadata_plans(
    symbols: list[object],
    pointer_size: int,
) -> None:
    """Propagate only chain lengths that source bodies actually need."""

    required = {id(symbol): set() for symbol in symbols}
    for symbol in symbols:
        for member in getattr(symbol, 'compiler_members', {}).values():
            source = getattr(member, 'compiler_member_source', None)
            if (
                getattr(member, 'compiler_member', None) == 'len'
                and getattr(getattr(source, 'type_spec', None), 'name', None)
                == 'chain'
                and getattr(source, 'identifier', None) in _chain_parameters(symbol)
            ):
                required[id(symbol)].add(source.identifier)

    changed = True
    while changed:
        changed = False
        for symbol in symbols:
            local_names = _chain_parameters(symbol)
            targets = getattr(symbol, 'call_targets', {})
            for node in _walk(getattr(symbol, 'body_node', None)):
                target = targets.get(id(node))
                if target is None:
                    continue
                target_required = required.get(id(target), set())
                if not target_required:
                    continue
                visible = [
                    parameter for parameter in getattr(
                        getattr(target, 'signature', None), 'parameters', ()
                    ) if not parameter.is_receiver
                ]
                for parameter, argument in zip(visible, _call_arguments(node)):
                    if parameter.name in target_required:
                        name = _identifier(argument)
                        if name in local_names and name not in required[id(symbol)]:
                            required[id(symbol)].add(name)
                            changed = True

    for symbol in symbols:
        build_abi_metadata_plan(symbol, pointer_size, required[id(symbol)])


__all__ = [
    'AbiMetadataPlan',
    'AbiParameter',
    'build_abi_metadata_plan',
    'build_abi_metadata_plans',
    'runtime_parameters',
]

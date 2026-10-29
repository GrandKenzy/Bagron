from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.frontend.objects.type import TypeSpec, ValueInfo

if TYPE_CHECKING:
    from core.storage import Storage


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    type_spec: TypeSpec
    has_default: bool = False
    # ``Len_t``/``Size_t`` are named parameters whose values are supplied by
    # the compiler from the data parameter immediately before them.
    is_length: bool = False
    is_size: bool = False
    length_of: str | None = None


# Kept as a type alias while the semantic model migrates to TypeSpec.
TypeInfo = TypeSpec


@dataclass(frozen=True)
class FunctionSignature:
    parameters: tuple[ParameterSpec, ...]
    return_type: TypeSpec


@dataclass
class FunctionSymbol:
    name: str
    signature: FunctionSignature
    scope: 'Storage | None' = None
    return_values: list[ValueInfo] = field(default_factory=list)
    return_node: object | None = None
    body_node: object | None = None
    body_supported_for_entrypoint: bool = True
    decorators: tuple[str, ...] = ()
    return_asm_node: object | None = None
    external_library: str | None = None
    calling_convention: str | None = None
    # Numeric `for` iterators are compiler-owned loop-local bindings.  They
    # are kept here because their lexical scope ends with the loop and they
    # therefore are not part of `scope.namespace` after semantic collection.
    loop_iterators: dict[str, TypeSpec] = field(default_factory=dict)
    # Ordinary locals keep lexical visibility in their Storage scopes, while
    # this manifest lets LLVM reserve static storage for every local at
    # function entry, including locals declared in nested control blocks.
    local_variables: dict[str, object] = field(default_factory=dict)

    @property
    def is_external(self) -> bool:
        return self.external_library is not None

    @property
    def is_assembler(self) -> bool:
        return 'assembler' in self.decorators

    @property
    def is_unsafe(self) -> bool:
        """Whether the function is allowed to cross the unsafe boundary."""
        return (
            self.is_external
            or self.is_assembler
            or 'unsafe' in self.decorators
        )

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
    # Instance methods receive the class object through an implicit first
    # parameter.  It is part of the generated ABI but hidden from source
    # calls.
    is_receiver: bool = False


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
    # A body may terminate without a source-level return when its last
    # reachable operation is a call to a ``Never`` function.  ``Never``
    # functions themselves are also marked as terminating by contract.
    body_terminates: bool = False
    never_call_nodes: set[int] = field(default_factory=set)
    decorators: tuple[str, ...] = ()
    is_inline: bool = False
    return_asm_node: object | None = None
    # A raw ``#prep`` body is emitted as a native function and must not also
    # receive an LLVM function body.  This is separate from
    # ``return_asm_node`` because void assembler functions do not need
    # ``return asm``.
    has_asm_body: bool = False
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
    # Module data is hidden from function/method scopes by default. A source
    # ``global name`` declaration records the explicit opt-in and is shared
    # with the function's Storage visibility gate.
    global_variables: set[str] = field(default_factory=set)
    # Methods are emitted under a reserved name while retaining their source
    # name for ``object.method(...)`` resolution.
    owner_type: str | None = None
    source_name: str | None = None
    is_method: bool = False
    is_static: bool = False
    receiver_name: str | None = None
    # Origin and visibility are retained after modules are flattened into the
    # compiler storage.  They let semantic lookup enforce module boundaries
    # without changing the emitted ABI name for public functions.
    module_path: object | None = None
    privacy: str = 'public'

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

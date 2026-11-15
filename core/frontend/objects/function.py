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
    # A unique parameter promises exclusive non-overlapping storage.
    is_unique: bool = False
    # Instance methods receive the class object through an implicit first
    # parameter.  It is part of the generated ABI but hidden from source
    # calls.
    is_receiver: bool = False

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
    # Resolved source-level calls used by the compiler's recursion analysis.
    # Symbols are kept by identity so aliases and methods retain their target.
    called_functions: list['FunctionSymbol'] = field(default_factory=list)
    # Resolved call-site targets let later flow analyses inspect the callee's
    # contract without trying to resolve source names a second time.
    call_targets: dict[int, 'FunctionSymbol'] = field(default_factory=dict)
    # Runtime-only parameters are derived after semantic analysis. Source
    # signatures never contain compiler metadata.
    abi_metadata_plan: object | None = None
    # Compiler member results are keyed by AST identity for backend lowering.
    compiler_members: dict[int, object] = field(default_factory=dict)
    tail_recursive: bool = False
    decorators: tuple[str, ...] = ()
    is_inline: bool = False
    # A raw ``#assembler`` body is emitted as a native function and must not also
    # receive an LLVM function body.
    has_asm_body: bool = False
    external_library: str | None = None
    external_domain: str | None = None
    calling_convention: str | None = None
    # Numeric `for` iterators are compiler-owned loop-local bindings.  They
    # are kept here because their lexical scope ends with the loop and they
    # therefore are not part of `scope.namespace` after semantic collection.
    loop_iterators: dict[str, TypeSpec] = field(default_factory=dict)
    # Ordinary locals keep lexical visibility in their Storage scopes, while
    # this manifest lets LLVM reserve static storage for every local at
    # function entry, including locals declared in nested control blocks.
    local_variables: dict[str, object] = field(default_factory=dict)
    # Flow-sensitive ownership metadata for resources and their field places.
    # The backend never reads this map; it exists only while validating source.
    buffer_states: dict[object, str] = field(default_factory=dict)
    # Places whose leak was already reported, so several exits report once.
    leak_reported: set[object] = field(default_factory=set)
    # Flow-sensitive proofs used by safe array indexing.  Facts are scoped to
    # the conditional or loop that established them and never reach LLVM.
    range_facts: list[object] = field(default_factory=list)
    # Conservative definite-write proofs for fixed local arrays.  The backend
    # may consume these facts in a later pass to elide redundant zeroing; the
    # analysis itself never changes the language's initialization semantics.
    definite_array_writes: set[str] = field(default_factory=set)
    # Per fixed-array parameter summary used by callers to distinguish an
    # input array from scratch/output storage.
    fixed_array_parameter_summary: dict[str, object] = field(default_factory=dict)
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
    method_key: tuple[str, str] | None = None
    # Semantic/source identity and backend identity are intentionally separate.
    llvm_name: str | None = None
    package_id: str | None = None
    # A lib2 declaration is backed by a native object already compiled by
    # Bagron.  It has no source body in the consuming project.
    is_compiled: bool = False

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

    @property
    def is_recursive(self) -> bool:
        return 'recursive' in self.decorators

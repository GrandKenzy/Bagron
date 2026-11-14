from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TypeSpec:
    """Resolved Bagron type information used by the frontend semantic pass."""

    name: str
    bit_width: int | None = None
    signed: bool | None = None
    pointer_level: int = 0
    array_depth: int = 0
    value_is_const: bool = False
    pointer_is_const: bool = False
    array_lengths: tuple[int | None, ...] = ()
    # ``unique`` is parsed as a type qualifier and consumed while building a
    # function parameter. It never becomes part of the runtime value type.
    is_unique: bool = False
    # Filled after semantic resolution for nominal types.  It is not part of
    # the source spelling; LLVM uses it to distinguish duplicate package APIs.
    nominal_key: str | None = None

    @property
    def canonical_name(self) -> str:
        name = self.name
        if self.name == 'Bint' and self.bit_width is not None:
            name = f'{name}({self.bit_width})'
        if self.is_unique:
            name = f'unique {name}'
        if self.array_lengths:
            suffix = ''.join(
                f'[{length}]' if length is not None else '[]'
                for length in self.array_lengths
            )
            return name + suffix
        return name + '[]' * self.array_depth


@dataclass
class OpaqueSymbol:
    """Nominal type with a compiler-known, but source-inaccessible, ABI."""

    name: str
    representation: TypeSpec
    privacy: str = 'public'
    module_path: object | None = None
    llvm_name: str | None = None
    package_id: str | None = None
    registry_key: str | None = None


@dataclass
class DefinedIntegerSymbol:
    """Public scalar integer introduced by ``#defint`` or ``#defuint``."""

    name: str
    bit_width: int
    signed: bool
    privacy: str = 'public'
    module_path: object | None = None
    llvm_name: str | None = None
    package_id: str | None = None
    registry_key: str | None = None


@dataclass(frozen=True)
class FieldSpec:
    """Semantic description of one field in an aggregate type."""

    name: str
    type_spec: TypeSpec
    value_info: ValueInfo | None = None
    # Class fields are inferred from ``self.field = value`` inside the single
    # initializer (``func __init__`` or ``func __frontend__``).  The AST is
    # retained so the backend can inline the initializer when emitting a
    # class value.
    initializer_node: object | None = None
    # Legacy bitfield offset metadata is retained for serialized compatibility
    # but is always ``None`` for the new structural ``fields`` aggregate.
    bit_offset: int | None = None
    # Class-only declaration owner, used to keep private fields out of
    # subclasses and unrelated classes.
    declaring_type: str | None = None


@dataclass
class AggregateSymbol:
    """Nominal declaration for a struct, mold, or fields type."""

    name: str
    kind: str
    fields: tuple[FieldSpec, ...] = ()
    inherited_fields: tuple[FieldSpec, ...] = ()
    is_class: bool = False
    # A frozen class may initialize its fields only through its single
    # initializer.  The frontend enforces the restriction; the backend keeps
    # the same struct-backed representation.
    is_frozen: bool = False
    privacy: str = 'public'
    # ``base_type`` remains for struct/mold compatibility; ``fields`` has no
    # implicit integer container.
    base_type: TypeSpec | None = None
    is_packed: bool = False
    is_volatile: bool = False
    alignment: int | None = None
    bit_order: str = 'lsb'
    signed_fields: bool = False
    # ``None`` means this aggregate has no initializer.  Classes use a tuple
    # of ParameterSpec-like objects here; structs and other aggregates leave
    # it unset.  The loose object type avoids a frontend-object import cycle.
    constructor_parameters: tuple[object, ...] | None = None
    # Classes may use exactly one initializer hook: ``__init__`` for explicit
    # construction or ``__frontend__`` for implicit source conversion.
    initializer_name: str | None = None
    # Class inheritance is compile-time metadata only.  The backend flattens
    # ``inherited_fields`` into the child layout; no parent pointer is stored.
    parent_type: str | None = None
    parent_initializer_name: str | None = None
    parent_initializer_arguments: tuple[object, ...] = ()
    # Module origin used by import visibility checks after type collection.
    module_path: object | None = None
    llvm_name: str | None = None
    package_id: str | None = None
    registry_key: str | None = None

    @property
    def all_fields(self) -> tuple[FieldSpec, ...]:
        """Return inherited fields followed by fields declared by this type."""
        return (*self.inherited_fields, *self.fields)


@dataclass(frozen=True)
class EnumMember:
    name: str
    value: int


@dataclass
class EnumSymbol:
    """Semantic declaration for an enum with an explicit integer base type."""

    name: str
    base_type: TypeSpec
    members: tuple[EnumMember, ...] = ()
    privacy: str = 'public'
    module_path: object | None = None
    llvm_name: str | None = None
    package_id: str | None = None
    registry_key: str | None = None


@dataclass(frozen=True)
class ValueInfo:
    """Type and provenance information for a resolved Bagron value."""

    type_spec: TypeSpec
    is_literal: bool = False
    identifier: str | None = None
    value: object = None
    items: tuple['ValueInfo', ...] = ()
    is_lvalue: bool = False
    address_origin: str | None = None
    address_of: str | None = None
    # Origin of the storage represented by an lvalue.  This is deliberately
    # separate from ``address_origin``: a local pointer variable may contain
    # the address of a global, while ``$pointer`` still takes the address of
    # the local pointer slot itself.
    storage_origin: str | None = None
    # Postfix operations between the base symbol and an address-of operator.
    # Entries are ('index', ValueInfo) or ('member', field_name).  Keeping the
    # path in semantic data lets the global emitter form a constant GEP too.
    address_path: tuple[tuple[str, object], ...] = ()
    # Fields limbs are ordinary members and therefore remain independently
    # addressable; this flag is retained for legacy value metadata.
    is_addressable: bool = True
    # Reading a pointer through raw union storage produces a pointer whose
    # provenance cannot be proven in safe Bagron code.
    pointer_provenance_unknown: bool = False
    # Name of the aggregate that owns the last member reached by this value.
    # Keeping this metadata lets assignment validation enforce @frozen through
    # indexing and known pointer aliases without adding runtime state.
    member_owner: str | None = None
    # A compiler-proven loop index may safely index the exact static array that
    # produced it.  These facts are intentionally narrow: they do not grant
    # bounds to arbitrary expressions or to arrays with runtime-only lengths.
    known_index_source: str | None = None
    known_index_path: tuple[tuple[str, object], ...] = ()
    known_index_length: int | None = None
    # Affine metadata for safe fixed-array indexing, such as ``index - 2``.
    range_base: str | None = None
    range_offset: int = 0
    # Safe ``unique`` calls require a compiler-proven storage identity. The
    # value is intentionally symbolic; no runtime ownership object is made.
    region_origin: str | None = None
    # A pointer marked here came from indexing Bagron's managed ``buffer``.
    # This is provenance for the extern boundary, not an ownership state.
    buffer_derived: bool = False
    # Symbolic compiler metadata has no address and is materialized only by
    # semantic consumers or the backend.
    compiler_member: str | None = None
    compiler_member_source: 'ValueInfo | None' = None

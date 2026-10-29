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

    @property
    def canonical_name(self) -> str:
        name = self.name
        if self.bit_width is not None:
            name = f'{name}<{self.bit_width}>'
        if self.array_lengths:
            suffix = ''.join(
                f'[{length}]' if length is not None else '[]'
                for length in self.array_lengths
            )
            return name + suffix
        return name + '[]' * self.array_depth


@dataclass(frozen=True)
class FieldSpec:
    """Semantic description of one field in an aggregate type."""

    name: str
    type_spec: TypeSpec
    value_info: ValueInfo | None = None
    # ``flags`` fields are logical bitfields rather than LLVM struct fields.
    # Their offset is fixed by declaration order once the aggregate has been
    # validated.  It remains ``None`` for struct/mold fields.
    bit_offset: int | None = None


@dataclass
class AggregateSymbol:
    """Nominal declaration for a struct, mold, or flags type."""

    name: str
    kind: str
    fields: tuple[FieldSpec, ...] = ()
    privacy: str = 'public'
    # ``flags`` owns a fixed, explicit integer container.  The remaining
    # metadata describes layout properties shared by all aggregate kinds.
    base_type: TypeSpec | None = None
    is_packed: bool = False
    is_volatile: bool = False
    alignment: int | None = None
    alignment_type: TypeSpec | None = None
    bit_order: str = 'lsb'


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
    # A bitfield is assignable but has no independently addressable storage.
    # This lets ``flags.value = 1`` remain legal while ``$flags.value`` is a
    # frontend error rather than an invalid LLVM address calculation.
    is_addressable: bool = True
    # Reading a pointer through raw union storage produces a pointer whose
    # provenance cannot be proven in safe Bagron code.
    pointer_provenance_unknown: bool = False

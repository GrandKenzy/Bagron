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

    @property
    def canonical_name(self) -> str:
        name = self.name
        if self.bit_width is not None:
            name = f'{name}<{self.bit_width}>'
        return name + '[]' * self.array_depth


@dataclass(frozen=True)
class FieldSpec:
    """Semantic description of one field in an aggregate type."""

    name: str
    type_spec: TypeSpec
    value_info: ValueInfo | None = None


@dataclass
class AggregateSymbol:
    """Nominal declaration for a struct, mold, or flags type."""

    name: str
    kind: str
    fields: tuple[FieldSpec, ...] = ()
    privacy: str = 'public'


@dataclass(frozen=True)
class EnumMember:
    name: str
    value: int


@dataclass
class EnumSymbol:
    """Semantic declaration for an enum with the fixed int32 base type."""

    name: str
    base_type: TypeSpec
    members: tuple[EnumMember, ...] = ()
    privacy: str = 'public'


@dataclass(frozen=True)
class ValueInfo:
    """Type information for a supported global initializer."""

    type_spec: TypeSpec
    is_literal: bool = False
    identifier: str | None = None
    value: object = None
    items: tuple['ValueInfo', ...] = ()

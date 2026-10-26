from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TypeInfo:
    name: str
    pointer_level: int = 0
    value_is_const: bool = False
    bit_width: int | None = None
    signed: bool | None = None


@dataclass(frozen=True)
class FunctionSignature:
    parameters: tuple[TypeInfo, ...]
    return_type: TypeInfo


@dataclass(frozen=True)
class FunctionSymbol:
    name: str
    signature: FunctionSignature

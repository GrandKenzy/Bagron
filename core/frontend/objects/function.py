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

    @property
    def is_assembler(self) -> bool:
        return 'assembler' in self.decorators

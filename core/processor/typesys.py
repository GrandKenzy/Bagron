"""Sistema de tipos intrínsecos del lenguaje.

Fuente única de verdad: tamaño, signo y categoría de cada tipo.
Ajusta aquí (p. ej. el ancho de `int` o la firmeza de `char`) y todo el
procesador se actualiza.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Final


class SemanticError(Exception):
    """Error semántico con posición opcional (si el token la expone)."""

    def __init__(self, message: str, token: Any = None) -> None:
        self.line = getattr(token, 'line', None)
        self.column = getattr(token, 'column', None)
        where = f'[línea {self.line}, col {self.column}] ' if self.line is not None else ''
        super().__init__(f'{where}{message}')


class Kind(Enum):
    INT = auto()
    FLOAT = auto()
    CHAR = auto()
    BOOL = auto()
    CHAIN = auto()
    VOID = auto()


@dataclass(frozen=True, slots=True)
class TypeInfo:
    name: str
    kind: Kind
    bits: int = 0
    signed: bool = False

    @property
    def min(self) -> int:
        return -(1 << (self.bits - 1)) if self.signed else 0

    @property
    def max(self) -> int:
        return (1 << (self.bits - 1)) - 1 if self.signed else (1 << self.bits) - 1


def _i(name: str, bits: int, signed: bool) -> TypeInfo:
    return TypeInfo(name, Kind.INT, bits, signed)


TYPES: Final[dict[str, TypeInfo]] = {
    t.name: t
    for t in (
        _i('int', 32, True), _i('int8', 8, True), _i('int16', 16, True),
        _i('int32', 32, True), _i('int64', 64, True),
        _i('uint', 32, False), _i('uint8', 8, False), _i('byte', 8, False),
        _i('uint16', 16, False), _i('uint32', 32, False), _i('uint64', 64, False),
        _i('wsize', 64, False),  # size_t
        TypeInfo('middle', Kind.FLOAT, 16),
        TypeInfo('float', Kind.FLOAT, 32),
        TypeInfo('double', Kind.FLOAT, 64),
        TypeInfo('char', Kind.CHAR, 8, False),  # sin signo, a diferencia de C
        TypeInfo('chain', Kind.CHAIN),
        TypeInfo('bool', Kind.BOOL),
        TypeInfo('void', Kind.VOID),
    )
}

# ptr / cptr son modificadores de puntero, no tipos base.
POINTER_KINDS: Final = frozenset({'ptr', 'cptr'})

_SCALARS: Final = frozenset({Kind.INT, Kind.FLOAT, Kind.CHAR, Kind.BOOL})
_FLOAT_FORMAT: Final = {16: '<e', 32: '<f', 64: '<d'}


def get_type(name: str, token: Any = None) -> TypeInfo:
    try:
        return TYPES[name]
    except KeyError:
        raise SemanticError(f"Tipo desconocido '{name}'", token) from None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _round_float(value: float, bits: int) -> float:
    """Redondea al ancho IEEE del tipo (middle=16, float=32, double=64)."""
    if bits == 64 or not math.isfinite(value):
        return float(value)
    fmt = _FLOAT_FORMAT[bits]
    try:
        return struct.unpack(fmt, struct.pack(fmt, value))[0]
    except OverflowError:
        return math.copysign(math.inf, value)  # igual que C


def _wrap(value: int, t: TypeInfo) -> int:
    value &= (1 << t.bits) - 1
    if t.signed and value >= 1 << (t.bits - 1):
        value -= 1 << t.bits
    return value


def fits_literal(value: Any, type_name: str) -> bool:
    """¿Es `value` un literal válido para el tipo? (valida rangos)."""
    t = get_type(type_name)
    if t.kind in (Kind.INT, Kind.CHAR):
        return isinstance(value, int) and not isinstance(value, bool) and t.min <= value <= t.max
    if t.kind is Kind.FLOAT:
        return _is_number(value) and math.isfinite(_round_float(float(value), t.bits))
    if t.kind is Kind.BOOL:
        return isinstance(value, bool)
    if t.kind is Kind.CHAIN:
        return isinstance(value, str)
    return False


def can_convert(target: str, source: str) -> bool:
    """Conversión escalar implícita (entero/char/flotante/bool entre sí)."""
    if target == source:
        return True
    return get_type(target).kind in _SCALARS and get_type(source).kind in _SCALARS


def can_assign_pointer(target: str, target_ptr: str | None, source: str, source_ptr: str | None) -> bool:
    """Reglas de punteros: ptr -> cptr sí, cptr -> ptr no (descartaría const)."""
    if target_ptr is None or source_ptr is None:
        return False
    if target_ptr == 'ptr' and source_ptr == 'cptr':
        return False
    return target == source or 'void' in (target, source)


NULL_TYPE: Final = 'Null'  # tipo del literal Null; su valor en runtime es None


def can_assign(target: str, target_ptr: str | None, source: str, source_ptr: str | None) -> bool:
    if source == NULL_TYPE:
        return target_ptr is not None  # Null solo cabe en ptr/cptr
    if target_ptr or source_ptr:
        return can_assign_pointer(target, target_ptr, source, source_ptr)
    return can_convert(target, source)


def convert(value: Any, target: str) -> Any:
    """Convierte el valor al tipo destino con semántica de C (trunca, envuelve)."""
    t = get_type(target)
    if t.kind in (Kind.INT, Kind.CHAR):
        if isinstance(value, float) and not math.isfinite(value):
            raise SemanticError(f'No se puede convertir {value} a {target}')
        return _wrap(int(value), t)
    if t.kind is Kind.FLOAT:
        return _round_float(float(value), t.bits)
    if t.kind is Kind.BOOL:
        return bool(value)
    return value
from __future__ import annotations

from collections.abc import Sequence

from llvmlite import ir

from core.frontend.objects import TypeSpec, ValueInfo


class LLVMTypeError(ValueError):
    """Raised when a Bagron type has no first-stage LLVM representation."""


_INTEGER_TYPES = {
    'int': 32,
    'int8': 8,
    'int16': 16,
    'int32': 32,
    'int64': 64,
    'uint': 32,
    'uint8': 8,
    'uint16': 16,
    'uint32': 32,
    'uint64': 64,
    'byte': 8,
}


def scalar_type(spec: TypeSpec) -> ir.Type:
    if spec.name == 'Bint' or spec.name == 'uBint':
        if spec.bit_width is None or spec.bit_width < 1:
            raise LLVMTypeError(f'Ancho invalido para {spec.canonical_name}')
        return ir.IntType(spec.bit_width)

    if spec.name in _INTEGER_TYPES:
        return ir.IntType(_INTEGER_TYPES[spec.name])
    if spec.name == 'bool':
        return ir.IntType(1)
    if spec.name == 'middle':
        return ir.HalfType()
    if spec.name == 'float':
        return ir.FloatType()
    if spec.name == 'double':
        return ir.DoubleType()

    raise LLVMTypeError(
        f'El tipo {spec.canonical_name!r} aun no tiene representacion LLVM'
    )


def llvm_type(spec: TypeSpec, array_lengths: Sequence[int] = ()) -> ir.Type:
    if spec.name in {'callptr', 'chain', 'void', 'Null'}:
        raise LLVMTypeError(
            f'El tipo {spec.canonical_name!r} queda fuera de la primera emision LLVM'
        )

    value_type = scalar_type(spec)
    for level in range(spec.pointer_level):
        value_type = value_type.as_pointer()

    if spec.array_depth:
        if len(array_lengths) != spec.array_depth:
            raise LLVMTypeError(
                f'No se pudo determinar el tamano de {spec.canonical_name}'
            )
        for length in reversed(tuple(array_lengths)):
            value_type = ir.ArrayType(value_type, length)

    return value_type


def _array_lengths(value: ValueInfo) -> tuple[int, ...]:
    if not value.items:
        return (0,)

    first = value.items[0]
    if first.type_spec.array_depth:
        return (len(value.items), *_array_lengths(first))
    return (len(value.items),)


def value_type(spec: TypeSpec, value: ValueInfo | None = None) -> ir.Type:
    lengths = _array_lengths(value) if value is not None and spec.array_depth else ()
    return llvm_type(spec, lengths)


def zero_value(spec: TypeSpec, value: ValueInfo | None = None) -> ir.Constant:
    target_type = value_type(spec, value)
    return ir.Constant(target_type, None)


def constant_value(spec: TypeSpec, value: ValueInfo) -> ir.Constant:
    target_type = value_type(spec, value)

    if spec.array_depth:
        if not value.items:
            return ir.Constant(target_type, [])
        element_spec = TypeSpec(
            name=spec.name,
            bit_width=spec.bit_width,
            signed=spec.signed,
            pointer_level=spec.pointer_level,
            array_depth=spec.array_depth - 1,
            value_is_const=spec.value_is_const,
        )
        elements = [constant_value(element_spec, item) for item in value.items]
        return ir.Constant(target_type, elements)

    if spec.pointer_level:
        if value.type_spec.name != 'Null':
            raise LLVMTypeError(
                f'El inicializador de {spec.canonical_name} no es Null'
            )
        return ir.Constant(target_type, None)

    if spec.name == 'bool':
        return ir.Constant(target_type, bool(value.value))
    if spec.name in _INTEGER_TYPES or spec.name in {'Bint', 'uBint'}:
        return ir.Constant(target_type, int(value.value))
    if spec.name in {'middle', 'float', 'double'}:
        return ir.Constant(target_type, float(value.value))

    raise LLVMTypeError(
        f'El valor de {spec.canonical_name!r} aun no puede emitirse como constante'
    )

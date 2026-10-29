from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from llvmlite import ir

from core.frontend.objects import AggregateSymbol, EnumSymbol, TypeSpec, ValueInfo

if TYPE_CHECKING:
    from llvmlite.ir import Module


class LLVMTypeError(ValueError):
    """Raised when a Bagron type has no first-stage LLVM representation."""


def _is_unsized_array(spec: TypeSpec) -> bool:
    return spec.array_depth > 0 and any(
        length is None for length in spec.array_lengths
    )


def _array_parameter_type(
    spec: TypeSpec,
    type_registry: 'LLVMTypeRegistry | None' = None,
) -> ir.Type:
    if (
        spec.pointer_level
        or spec.array_depth != 1
    ):
        raise LLVMTypeError(
            f'El parametro array {spec.canonical_name} debe ser un array '
            'unidimensional sin puntero'
        )
    element_spec = TypeSpec(
        name=spec.name,
        bit_width=spec.bit_width,
        signed=spec.signed,
        value_is_const=spec.value_is_const,
        pointer_is_const=spec.pointer_is_const,
    )
    if type_registry is not None:
        element_type = type_registry.resolve(element_spec)
    else:
        element_type = scalar_type(element_spec)
    return element_type.as_pointer()


class LLVMTypeRegistry:
    """Map Bagron nominal types to identified LLVM struct types."""

    def __init__(self, module: Module, symbols: dict[str, object]):
        self._types: dict[str, ir.Type] = {}
        self._fields: dict[str, dict[str, int]] = {}
        aggregates: list[AggregateSymbol] = []

        for name, symbol in symbols.items():
            if isinstance(symbol, EnumSymbol):
                self._types[name] = scalar_type(symbol.base_type)
            elif isinstance(symbol, AggregateSymbol):
                self._types[name] = module.context.get_identified_type(
                    name,
                    packed=symbol.kind == 'flags',
                )
                self._fields[name] = {
                    field.name: index
                    for index, field in enumerate(symbol.fields)
                }
                aggregates.append(symbol)

        for aggregate in aggregates:
            llvm_type = self._types[aggregate.name]
            if not isinstance(llvm_type, ir.IdentifiedStructType):
                raise LLVMTypeError(
                    f'El tipo agregado {aggregate.name} no tiene una definicion LLVM'
                )
            fields = [self.resolve(field.type_spec) for field in aggregate.fields]
            llvm_type.set_body(*fields)

    def field_index(self, type_name: str, field_name: str) -> int | None:
        return self._fields.get(type_name, {}).get(field_name)

    def resolve(
        self,
        spec: TypeSpec,
        array_lengths: Sequence[int] = (),
    ) -> ir.Type:
        if _is_unsized_array(spec):
            return _array_parameter_type(spec, self)
        if spec.name == 'void':
            if spec.array_depth:
                raise LLVMTypeError('void no puede usarse como array')
            value_type = ir.IntType(8) if spec.pointer_level else ir.VoidType()
            for _ in range(spec.pointer_level):
                value_type = value_type.as_pointer()
            return value_type
        if spec.name == 'chain':
            if spec.pointer_level or spec.array_depth:
                raise LLVMTypeError(
                    'chain no puede combinarse con punteros ni arrays'
                )
            # In function signatures a chain is a read-only pointer to its
            # static, NUL-terminated bytes.  Locals and globals still use
            # value_type(), which preserves their concrete array storage.
            return ir.IntType(8).as_pointer()
        value_type = self._types.get(spec.name)
        if value_type is None:
            value_type = scalar_type(spec)

        for _ in range(spec.pointer_level):
            value_type = value_type.as_pointer()

        if spec.array_depth:
            lengths = _resolve_array_lengths(spec, array_lengths)
            if len(lengths) != spec.array_depth:
                raise LLVMTypeError(
                    f'No se pudo determinar el tamano de {spec.canonical_name}'
                )
            for length in reversed(lengths):
                value_type = ir.ArrayType(value_type, length)
        return value_type


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
    if spec.name == 'char':
        return ir.IntType(8)
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


def llvm_type(
    spec: TypeSpec,
    array_lengths: Sequence[int] = (),
    type_registry: LLVMTypeRegistry | None = None,
) -> ir.Type:
    if type_registry is not None:
        return type_registry.resolve(spec, array_lengths)
    if _is_unsized_array(spec):
        return _array_parameter_type(spec)
    if spec.name == 'void':
        if spec.array_depth:
            raise LLVMTypeError('void no puede usarse como array')
        value_type = ir.IntType(8) if spec.pointer_level else ir.VoidType()
        for _ in range(spec.pointer_level):
            value_type = value_type.as_pointer()
        return value_type
    if spec.name in {'callptr', 'Null'}:
        raise LLVMTypeError(
            f'El tipo {spec.canonical_name!r} queda fuera de la primera emision LLVM'
        )
    if spec.name == 'chain':
        if spec.pointer_level or spec.array_depth:
            raise LLVMTypeError(
                'chain no puede combinarse con punteros ni arrays'
            )
        return ir.IntType(8).as_pointer()

    value_type = scalar_type(spec)
    for level in range(spec.pointer_level):
        value_type = value_type.as_pointer()

    if spec.array_depth:
        lengths = _resolve_array_lengths(spec, array_lengths)
        if len(lengths) != spec.array_depth:
            raise LLVMTypeError(
                f'No se pudo determinar el tamano de {spec.canonical_name}'
            )
        for length in reversed(lengths):
            value_type = ir.ArrayType(value_type, length)

    return value_type


def _resolve_array_lengths(
    spec: TypeSpec,
    inferred: Sequence[int] = (),
) -> tuple[int, ...]:
    if not spec.array_depth:
        return ()

    declared = spec.array_lengths
    if declared and len(declared) != spec.array_depth:
        raise LLVMTypeError(
            f'La declaracion de {spec.canonical_name} tiene dimensiones invalidas'
        )

    if inferred and len(inferred) != spec.array_depth:
        raise LLVMTypeError(
            f'No se pudo determinar el tamano de {spec.canonical_name}'
        )

    lengths: list[int] = []
    for index in range(spec.array_depth):
        declared_length = declared[index] if declared else None
        inferred_length = inferred[index] if inferred else None
        length = declared_length if declared_length is not None else inferred_length
        if length is None or length < 1:
            raise LLVMTypeError(
                f'No se pudo determinar el tamano de {spec.canonical_name}'
            )
        lengths.append(length)
    return tuple(lengths)


def _string_bytes(value: object, *, ascii_only: bool = False) -> bytes:
    if not isinstance(value, str):
        raise LLVMTypeError('Se esperaba un literal de cadena')
    try:
        return value.encode('ascii' if ascii_only else 'utf-8')
    except UnicodeEncodeError as error:
        raise LLVMTypeError('Un literal char solo puede contener ASCII') from error


def _array_lengths(value: ValueInfo) -> tuple[int, ...]:
    if (
        value.type_spec.name == 'chain'
        and value.type_spec.array_depth == 0
        and value.is_literal
    ):
        return (len(_string_bytes(value.value)),)
    if not value.items:
        return (0,)

    first = value.items[0]
    if first.type_spec.array_depth:
        return (len(value.items), *_array_lengths(first))
    return (len(value.items),)


def value_type(
    spec: TypeSpec,
    value: ValueInfo | None = None,
    type_registry: LLVMTypeRegistry | None = None,
) -> ir.Type:
    if _is_unsized_array(spec):
        return _array_parameter_type(spec, type_registry)
    if spec.name == 'void' and spec.pointer_level == 0:
        raise LLVMTypeError('void no puede usarse como almacenamiento')
    if spec.name == 'chain':
        if value is None:
            raise LLVMTypeError('chain requiere un inicializador')
        data = _string_bytes(value.value)
        return ir.ArrayType(ir.IntType(8), len(data) + 1)
    lengths = _array_lengths(value) if value is not None and spec.array_depth else ()
    return llvm_type(spec, lengths, type_registry)


def zero_value(
    spec: TypeSpec,
    value: ValueInfo | None = None,
    type_registry: LLVMTypeRegistry | None = None,
) -> ir.Constant:
    target_type = value_type(spec, value, type_registry)
    return ir.Constant(target_type, None)


def constant_value(
    spec: TypeSpec,
    value: ValueInfo,
    type_registry: LLVMTypeRegistry | None = None,
) -> ir.Constant:
    target_type = value_type(spec, value, type_registry)

    if spec.name == 'chain':
        data = _string_bytes(value.value)
        byte_type = ir.IntType(8)
        values = [ir.Constant(byte_type, item) for item in (*data, 0)]
        return ir.Constant(target_type, values)

    if spec.array_depth:
        if (
            value.type_spec.name == 'chain'
            and value.type_spec.array_depth == 0
            and value.is_literal
        ):
            data = _string_bytes(
                value.value,
                ascii_only=spec.name == 'char',
            )
            if len(data) > target_type.count:
                raise LLVMTypeError(
                    f'El literal excede el tamano de {spec.canonical_name}'
                )
            element_type = ir.IntType(8)
            elements = [ir.Constant(element_type, item) for item in data]
            elements.extend(
                ir.Constant(element_type, 0)
                for _ in range(target_type.count - len(elements))
            )
            return ir.Constant(target_type, elements)
        if not value.items:
            return ir.Constant(target_type, [])
        element_spec = TypeSpec(
            name=spec.name,
            bit_width=spec.bit_width,
            signed=spec.signed,
            pointer_level=spec.pointer_level,
            array_depth=spec.array_depth - 1,
            value_is_const=spec.value_is_const,
            array_lengths=spec.array_lengths[1:] if spec.array_lengths else (),
        )
        elements = [
            constant_value(element_spec, item, type_registry)
            for item in value.items
        ]
        elements.extend(
            ir.Constant(target_type.element, None)
            for _ in range(target_type.count - len(elements))
        )
        return ir.Constant(target_type, elements)

    if spec.pointer_level:
        if value.type_spec.name != 'Null':
            raise LLVMTypeError(
                f'El inicializador de {spec.canonical_name} no es Null'
            )
        return ir.Constant(target_type, None)

    if spec.name == 'bool':
        return ir.Constant(target_type, bool(value.value))
    if spec.name in {'char', 'byte'} and value.type_spec.name == 'chain':
        data = _string_bytes(value.value, ascii_only=spec.name == 'char')
        if len(data) != 1:
            raise LLVMTypeError(
                f'El literal para {spec.name} debe contener exactamente un byte'
            )
        return ir.Constant(target_type, data[0])
    if spec.name in _INTEGER_TYPES or spec.name in {'Bint', 'uBint'}:
        return ir.Constant(target_type, int(value.value))
    if spec.name in {'middle', 'float', 'double'}:
        return ir.Constant(target_type, float(value.value))

    raise LLVMTypeError(
        f'El valor de {spec.canonical_name!r} aun no puede emitirse como constante'
    )

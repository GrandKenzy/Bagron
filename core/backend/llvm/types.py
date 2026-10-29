from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
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


@dataclass(frozen=True)
class AggregateLayout:
    """LLVM storage details for one nominal Bagron aggregate.

    Every named type uses an outer identified structure and an inner literal
    payload.  The small indirection lets an alignment carrier raise the ABI
    alignment without changing the public nominal type, while keeping packed
    payloads and union storage explicit.
    """

    symbol: AggregateSymbol
    llvm_type: ir.IdentifiedStructType
    payload_type: ir.LiteralStructType
    payload_index: int
    field_paths: dict[str, tuple[int, ...]]
    storage_path: tuple[int, ...] | None
    backing_type: ir.Type | None
    alignment: int
    size: int


class LLVMTypeRegistry:
    """Map Bagron nominal aggregates to ABI-aware LLVM layouts."""

    def __init__(
        self,
        module: Module,
        symbols: dict[str, object],
        target_data: object | None = None,
    ):
        self.module = module
        self.target_data = target_data
        self._types: dict[str, ir.Type] = {}
        self._symbols: dict[str, AggregateSymbol] = {}
        self._layouts: dict[str, AggregateLayout] = {}

        aggregates: list[AggregateSymbol] = []
        for name, symbol in symbols.items():
            if isinstance(symbol, EnumSymbol):
                self._types[name] = scalar_type(symbol.base_type)
            elif isinstance(symbol, AggregateSymbol):
                llvm_type = module.context.get_identified_type(name)
                self._types[name] = llvm_type
                self._symbols[name] = symbol
                aggregates.append(symbol)

        for aggregate in self._dependency_order(aggregates):
            self._define_aggregate(aggregate)

    def _dependency_order(
        self,
        aggregates: Sequence[AggregateSymbol],
    ) -> list[AggregateSymbol]:
        known = {aggregate.name: aggregate for aggregate in aggregates}
        ordered: list[AggregateSymbol] = []
        visiting: list[str] = []
        visited: set[str] = set()

        def visit(aggregate: AggregateSymbol) -> None:
            if aggregate.name in visiting:
                cycle = ' -> '.join((*visiting[visiting.index(aggregate.name):], aggregate.name))
                raise LLVMTypeError(f'Ciclo de agregados por valor: {cycle}')
            if aggregate.name in visited:
                return
            visiting.append(aggregate.name)
            for field in aggregate.fields:
                if field.type_spec.pointer_level:
                    continue
                dependency = known.get(field.type_spec.name)
                if dependency is not None:
                    visit(dependency)
            visiting.pop()
            visited.add(aggregate.name)
            ordered.append(aggregate)

        for aggregate in aggregates:
            visit(aggregate)
        return ordered

    def _abi_size(self, value_type: ir.Type) -> int:
        if self.target_data is None:
            raise LLVMTypeError('El layout del target es necesario para agregados')
        return value_type.get_abi_size(self.target_data, self.module.context)

    def _abi_alignment(self, value_type: ir.Type) -> int:
        if self.target_data is None:
            raise LLVMTypeError('El layout del target es necesario para agregados')
        return value_type.get_abi_alignment(self.target_data, self.module.context)

    @staticmethod
    def _alignment_carrier(alignment: int) -> ir.ArrayType:
        # A zero-length vector array contributes alignment but no bytes.  It
        # is an LLVM-native way to model ``aligned(N)`` on an identified type.
        return ir.ArrayType(ir.VectorType(ir.IntType(8), alignment), 0)

    def _requested_alignment(self, symbol: AggregateSymbol) -> int | None:
        return symbol.alignment

    def _effective_alignment(
        self,
        symbol: AggregateSymbol,
        payload_type: ir.LiteralStructType,
        natural_alignment: int | None = None,
    ) -> int:
        payload_alignment = self._abi_alignment(payload_type)
        natural = natural_alignment or payload_alignment
        requested = self._requested_alignment(symbol)
        if requested is not None and requested < natural and not symbol.is_packed:
            raise LLVMTypeError(
                f'El @align de {symbol.name} no puede reducir su alineacion natural '
                f'de {natural}'
            )
        if symbol.is_packed:
            return requested or 1
        return max(natural, requested or 1)

    def _set_outer_body(
        self,
        llvm_type: ir.IdentifiedStructType,
        payload_type: ir.LiteralStructType,
        alignment: int,
    ) -> int:
        payload_alignment = self._abi_alignment(payload_type)
        if alignment > payload_alignment:
            llvm_type.set_body(self._alignment_carrier(alignment), payload_type)
            return 1
        llvm_type.set_body(payload_type)
        return 0

    def _define_aggregate(self, symbol: AggregateSymbol) -> None:
        llvm_type = self._types.get(symbol.name)
        if not isinstance(llvm_type, ir.IdentifiedStructType):
            raise LLVMTypeError(
                f'El tipo agregado {symbol.name} no tiene una definicion LLVM'
            )

        field_paths: dict[str, tuple[int, ...]] = {}
        storage_path: tuple[int, ...] | None = None
        backing_type: ir.Type | None = None
        if symbol.kind == 'struct':
            fields = [self.resolve(field.type_spec) for field in symbol.fields]
            payload = ir.LiteralStructType(fields, packed=symbol.is_packed)
            alignment = self._effective_alignment(symbol, payload)
            payload_index = self._set_outer_body(llvm_type, payload, alignment)
            field_paths = {
                field.name: (payload_index, index)
                for index, field in enumerate(symbol.fields)
            }
        elif symbol.kind == 'mold':
            member_types = [self.resolve(field.type_spec) for field in symbol.fields]
            member_sizes = [self._abi_size(value_type) for value_type in member_types]
            member_alignments = [
                self._abi_alignment(value_type)
                for value_type in member_types
            ]
            if not member_sizes:
                raise LLVMTypeError(f'El mold {symbol.name} no puede estar vacio')
            storage = ir.ArrayType(ir.IntType(8), max(member_sizes))
            payload = ir.LiteralStructType([storage], packed=symbol.is_packed)
            natural_alignment = 1 if symbol.is_packed else max(member_alignments)
            alignment = self._effective_alignment(
                symbol,
                payload,
                natural_alignment=natural_alignment,
            )
            payload_index = self._set_outer_body(llvm_type, payload, alignment)
            storage_path = (payload_index, 0)
        elif symbol.kind == 'flags':
            if symbol.base_type is None:
                raise LLVMTypeError(f'El flags {symbol.name} no tiene tipo base')
            backing_type = scalar_type(symbol.base_type)
            payload = ir.LiteralStructType([backing_type], packed=symbol.is_packed)
            alignment = self._effective_alignment(symbol, payload)
            payload_index = self._set_outer_body(llvm_type, payload, alignment)
            storage_path = (payload_index, 0)
        else:
            raise LLVMTypeError(f'Clase de agregado desconocida: {symbol.kind}')

        self._layouts[symbol.name] = AggregateLayout(
            symbol=symbol,
            llvm_type=llvm_type,
            payload_type=payload,
            payload_index=payload_index,
            field_paths=field_paths,
            storage_path=storage_path,
            backing_type=backing_type,
            alignment=self._abi_alignment(llvm_type),
            size=self._abi_size(llvm_type),
        )

    def layout(self, type_name: str) -> AggregateLayout | None:
        return self._layouts.get(type_name)

    def aggregate(self, type_name: str) -> AggregateSymbol | None:
        return self._symbols.get(type_name)

    def field_spec(self, type_name: str, field_name: str):
        symbol = self._symbols.get(type_name)
        if symbol is None:
            return None
        return next((field for field in symbol.fields if field.name == field_name), None)

    def field_path(self, type_name: str, field_name: str) -> tuple[int, ...] | None:
        layout = self._layouts.get(type_name)
        if layout is None:
            return None
        return layout.field_paths.get(field_name)

    def field_index(self, type_name: str, field_name: str) -> int | None:
        """Compatibility helper for direct struct fields.

        New code uses ``field_path`` because alignment carriers can insert an
        extra GEP level.
        """
        path = self.field_path(type_name, field_name)
        return path[-1] if path else None

    def storage_path(self, type_name: str) -> tuple[int, ...] | None:
        layout = self._layouts.get(type_name)
        return layout.storage_path if layout is not None else None

    def flags_backing_type(self, type_name: str) -> ir.Type | None:
        layout = self._layouts.get(type_name)
        return layout.backing_type if layout is not None else None

    def is_volatile(self, type_name: str) -> bool:
        layout = self._layouts.get(type_name)
        return bool(layout and layout.symbol.is_volatile)

    def abi_alignment(self, value_type: ir.Type) -> int:
        return self._abi_alignment(value_type)

    def alignment_for_spec(self, spec: TypeSpec) -> int:
        return self._abi_alignment(self.resolve(spec))

    def default_constant(self, spec: TypeSpec) -> ir.Constant:
        """Return the deterministic default value for a Bagron storage type."""
        target_type = self.resolve(spec)
        if spec.pointer_level:
            return ir.Constant(target_type, None)
        if spec.array_depth:
            if not isinstance(target_type, ir.ArrayType):
                raise LLVMTypeError(
                    f'El array {spec.canonical_name} no tiene tipo LLVM fijo'
                )
            element_spec = TypeSpec(
                name=spec.name,
                bit_width=spec.bit_width,
                signed=spec.signed,
                pointer_level=spec.pointer_level,
                array_depth=spec.array_depth - 1,
                value_is_const=spec.value_is_const,
                pointer_is_const=spec.pointer_is_const,
                array_lengths=spec.array_lengths[1:] if spec.array_lengths else (),
            )
            element = self.default_constant(element_spec)
            return ir.Constant(target_type, [element] * target_type.count)

        layout = self._layouts.get(spec.name)
        if layout is None:
            return ir.Constant(target_type, None)
        if layout.symbol.kind == 'mold':
            return ir.Constant(target_type, None)
        if layout.symbol.kind == 'flags':
            if not isinstance(layout.backing_type, ir.IntType):
                raise LLVMTypeError(f'El flags {spec.name} no tiene entero base')
            value = 0
            for field in layout.symbol.fields:
                width = self._integer_width(field.type_spec)
                if width is None or field.bit_offset is None or field.value_info is None:
                    raise LLVMTypeError(
                        f'El campo {spec.name}.{field.name} no tiene layout de bits'
                    )
                mask = (1 << width) - 1
                value |= (int(field.value_info.value) & mask) << field.bit_offset
            payload = ir.Constant(
                layout.payload_type,
                [ir.Constant(layout.backing_type, value)],
            )
        else:
            payload = ir.Constant(
                layout.payload_type,
                [self.default_constant(field.type_spec) for field in layout.symbol.fields],
            )
        outer_values: list[ir.Constant] = []
        if layout.payload_index:
            outer_values.append(ir.Constant(target_type.elements[0], None))
        outer_values.append(payload)
        return ir.Constant(target_type, outer_values)

    @staticmethod
    def _integer_width(spec: TypeSpec) -> int | None:
        if spec.name == 'bool':
            return 1
        if spec.name in {'Bint', 'uBint', 'usize', 'isize'}:
            return spec.bit_width
        return _INTEGER_TYPES.get(spec.name)

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
    if spec.name in {'Bint', 'uBint', 'usize', 'isize'}:
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


def default_value(
    spec: TypeSpec,
    value: ValueInfo | None = None,
    type_registry: LLVMTypeRegistry | None = None,
) -> ir.Constant:
    """Return storage defaults, including declarative ``flags`` bits."""
    if type_registry is not None and not _is_unsized_array(spec) and (
        spec.array_depth or type_registry.layout(spec.name) is not None
    ):
        return type_registry.default_constant(spec)
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
    if spec.name in _INTEGER_TYPES or spec.name in {
        'Bint', 'uBint', 'usize', 'isize'
    }:
        return ir.Constant(target_type, int(value.value))
    if spec.name in {'middle', 'float', 'double'}:
        return ir.Constant(target_type, float(value.value))

    raise LLVMTypeError(
        f'El valor de {spec.canonical_name!r} aun no puede emitirse como constante'
    )

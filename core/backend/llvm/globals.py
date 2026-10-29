from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from core.backend.llvm.types import (
    LLVMTypeError,
    LLVMTypeRegistry,
    constant_value,
    default_value,
    value_type,
)
from core.frontend.objects import ValueInfo, Variable

if TYPE_CHECKING:
    from llvmlite import ir
    from core.storage import Storage


class GlobalEmissionError(ValueError):
    """Raised when a global cannot be represented as a static LLVM initializer."""


class GlobalEmitter:
    def __init__(self, module: ir.Module, type_registry: LLVMTypeRegistry | None = None):
        self.module = module
        self.type_registry = type_registry
        self._resolving: list[str] = []
        self._string_literals: dict[str, object] = {}

    def _string_pointer(self, value: str):
        from llvmlite import ir

        global_value = self._string_literals.get(value)
        if global_value is None:
            data = value.encode('utf-8')
            byte_type = ir.IntType(8)
            array_type = ir.ArrayType(byte_type, len(data) + 1)
            global_value = ir.GlobalVariable(
                self.module,
                array_type,
                name=f'__bagron_global_string_{len(self._string_literals)}',
            )
            global_value.linkage = 'private'
            global_value.global_constant = True
            global_value.initializer = ir.Constant(
                array_type,
                [ir.Constant(byte_type, byte) for byte in (*data, 0)],
            )
            self._string_literals[value] = global_value

        index_type = ir.IntType(32)
        return global_value.gep([
            ir.Constant(index_type, 0),
            ir.Constant(index_type, 0),
        ])

    def _aggregate_constant(self, spec, value: ValueInfo):
        from llvmlite import ir

        if self.type_registry is None:
            raise GlobalEmissionError(
                f'El agregado {spec.canonical_name} requiere un registro de tipos'
            )
        layout = self.type_registry.layout(spec.name)
        if layout is None or layout.symbol.kind != 'struct':
            raise GlobalEmissionError(
                f'El agregado {spec.canonical_name} no admite un inicializador '
                'frontend global'
            )
        if not value.items:
            if not value.is_literal:
                raise GlobalEmissionError(
                    f'El inicializador frontend de {spec.name} debe ser constante '
                    'en una variable global'
                )
            return self.type_registry.default_constant(spec)
        if len(value.items) != len(layout.symbol.all_fields):
            raise GlobalEmissionError(
                f'El agregado {spec.canonical_name} no tiene todos sus campos'
            )

        field_values = []
        for field, field_value in zip(layout.symbol.all_fields, value.items):
            if field.type_spec.name == 'chain':
                if not field_value.is_literal or not isinstance(field_value.value, str):
                    raise GlobalEmissionError(
                        f'El campo {spec.name}.{field.name} requiere un chain constante'
                    )
                field_values.append(self._string_pointer(field_value.value))
                continue
            if (
                self.type_registry.layout(field.type_spec.name) is not None
                and field.type_spec.pointer_level == 0
                and field.type_spec.array_depth == 0
            ):
                field_values.append(
                    self._aggregate_constant(field.type_spec, field_value)
                )
                continue
            field_values.append(
                constant_value(field.type_spec, field_value, self.type_registry)
            )

        payload = ir.Constant(layout.payload_type, field_values)
        target_type = value_type(spec, value, self.type_registry)
        outer_values = []
        if layout.payload_index:
            outer_values.append(ir.Constant(target_type.elements[0], None))
        outer_values.append(payload)
        return ir.Constant(target_type, outer_values)

    def emit_storage(self, storage: Storage) -> None:
        # Declare every global before resolving initializers.  This makes a
        # static address such as ``p *: int = $x`` independent of declaration
        # order at the LLVM layer and lets the initializer refer to a global
        # that appears later in the source file.
        for symbol in storage.namespace.values():
            if isinstance(symbol, Variable):
                self._declare_symbol(storage, symbol)

        for symbol in storage.namespace.values():
            if isinstance(symbol, Variable):
                self._initialize_symbol(storage, symbol)

    def _constant_value(self, storage: Storage, symbol: Variable) -> ValueInfo | None:
        if symbol.name in self._resolving:
            chain = ' -> '.join((*self._resolving, symbol.name))
            raise GlobalEmissionError(f'Ciclo de inicializacion global: {chain}')

        self._resolving.append(symbol.name)
        try:
            if not symbol.initialized:
                has_aggregate_default = (
                    self.type_registry is not None
                    and symbol.type_spec is not None
                    and self.type_registry.layout(symbol.type_spec.name) is not None
                )
                if symbol.value_is_const and not has_aggregate_default:
                    raise GlobalEmissionError(
                        f'El global const {symbol.name} no tiene inicializador'
                    )
                return None

            value = symbol.value_info
            if value is None:
                raise GlobalEmissionError(
                    f'No existe un valor semantico para el global {symbol.name}'
                )

            return self._resolve_value(storage, value)
        finally:
            self._resolving.pop()

    def _resolve_value(self, storage: Storage, value: ValueInfo) -> ValueInfo:
        if value.identifier is not None and not value.is_literal:
            target = storage.namespace.get(value.identifier)
            if not isinstance(target, Variable):
                raise GlobalEmissionError(
                    f'El inicializador no referencia un global: {value.identifier}'
                )
            if not target.value_is_const:
                raise GlobalEmissionError(
                    f'El global mutable {target.name} no puede usarse como inicializador estatico'
                )
            resolved = self._constant_value(storage, target)
            if resolved is None:
                raise GlobalEmissionError(
                    f'El global const {target.name} no tiene un valor estatico'
                )
            return resolved

        if not value.items:
            return value

        resolved_items = tuple(
            self._resolve_value(storage, item)
            for item in value.items
        )
        return replace(value, value=resolved_items, items=resolved_items)

    def _declare_symbol(self, storage: Storage, symbol: Variable) -> object:
        if symbol.type_spec is None:
            raise GlobalEmissionError(f'El global {symbol.name} no tiene TypeSpec')

        if symbol.type_spec.name == 'callptr':
            raise GlobalEmissionError(
                f'callptr global aun no tiene emision LLVM: {symbol.name}'
            )

        try:
            value = symbol.value_info
            target_type = value_type(
                symbol.type_spec,
                value,
                self.type_registry,
            )
            initializer = default_value(
                symbol.type_spec,
                value,
                self.type_registry,
            )
        except LLVMTypeError as error:
            raise GlobalEmissionError(f'{symbol.name}: {error}') from error

        if symbol.name in self.module.globals:
            raise GlobalEmissionError(f'Simbolo LLVM duplicado: {symbol.name}')

        from llvmlite import ir

        global_value = ir.GlobalVariable(
            self.module,
            target_type,
            symbol.name,
        )

        global_value.initializer = initializer
        global_value.global_constant = symbol.value_is_const
        if self.type_registry is not None:
            global_value.align = self.type_registry.abi_alignment(target_type)
        if symbol.privacy == 'private':
            global_value.linkage = 'internal'
        return global_value

    def _address_initializer(
        self,
        symbol: Variable,
        value: ValueInfo,
    ) -> object:
        from llvmlite import ir

        target_name = value.address_of
        if not target_name:
            raise GlobalEmissionError(
                f'El inicializador de {symbol.name} no tiene un destino de direccion'
            )

        target = self.module.globals.get(target_name)
        if target is None:
            raise GlobalEmissionError(
                f'El destino de la direccion global no existe: {target_name}'
            )

        destination = self.module.globals.get(symbol.name)
        if destination is None:
            raise GlobalEmissionError(
                f'El global {symbol.name} no tiene declaracion LLVM'
            )
        # A GlobalVariable is itself a constant pointer value in LLVM IR.
        # Passing it directly (instead of wrapping it in ir.Constant) avoids
        # serializing the complete global definition inside the initializer.
        address = target
        for operation, payload in value.address_path:
            pointee = address.type.pointee
            if operation == 'index':
                index_info = payload
                if not getattr(index_info, 'is_literal', False):
                    raise GlobalEmissionError(
                        f'El indice de la direccion global {target_name} '
                        'debe ser un literal'
                    )
                try:
                    index = int(index_info.value)
                except (TypeError, ValueError) as error:
                    raise GlobalEmissionError(
                        f'El indice de la direccion global {target_name} no es entero'
                    ) from error
                if not isinstance(pointee, ir.ArrayType):
                    raise GlobalEmissionError(
                        f'La direccion global {target_name} no indexa un array estatico'
                    )
                address = address.gep([
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), index),
                ])
                continue

            if operation == 'member':
                if not isinstance(pointee, ir.IdentifiedStructType):
                    raise GlobalEmissionError(
                        f'La direccion global {target_name} no referencia un struct'
                    )
                layout = (
                    self.type_registry.layout(pointee.name)
                    if self.type_registry is not None
                    else None
                )
                field = (
                    self.type_registry.field_spec(pointee.name, str(payload))
                    if self.type_registry is not None
                    else None
                )
                if layout is None or field is None:
                    raise GlobalEmissionError(
                        f'El miembro {payload} no existe en {pointee.name}'
                    )
                if layout.symbol.kind == 'flags':
                    raise GlobalEmissionError(
                        f'El campo de flags {pointee.name}.{payload} no tiene direccion'
                    )
                if layout.symbol.kind == 'mold':
                    if layout.storage_path is None:
                        raise GlobalEmissionError(
                            f'El mold {pointee.name} no tiene almacenamiento LLVM'
                        )
                    address = address.gep([
                        ir.Constant(ir.IntType(32), 0),
                        *(
                            ir.Constant(ir.IntType(32), item)
                            for item in layout.storage_path
                        ),
                    ]).bitcast(self.type_registry.resolve(field.type_spec).as_pointer())
                else:
                    path = self.type_registry.field_path(pointee.name, str(payload))
                    if path is None:
                        raise GlobalEmissionError(
                            f'El miembro {payload} no tiene ruta LLVM en {pointee.name}'
                        )
                    address = address.gep([
                        ir.Constant(ir.IntType(32), 0),
                        *(ir.Constant(ir.IntType(32), item) for item in path),
                    ])
                continue

            raise GlobalEmissionError(
                f'Operacion de direccion global no soportada: {operation}'
            )

        if address.type != destination.type.pointee:
            raise GlobalEmissionError(
                f'La direccion de {target_name} no coincide con '
                f'{symbol.type_spec.canonical_name}'
            )
        return address

    def _initialize_symbol(self, storage: Storage, symbol: Variable) -> None:
        destination = self.module.globals.get(symbol.name)
        if destination is None:
            raise GlobalEmissionError(
                f'El global {symbol.name} no tiene declaracion LLVM'
            )

        try:
            value = self._constant_value(storage, symbol)
            if value is None:
                return
            if value.address_of is not None:
                initializer = self._address_initializer(symbol, value)
            elif (
                self.type_registry is not None
                and getattr(
                    self.type_registry.aggregate(symbol.type_spec.name),
                    'initializer_name',
                    None,
                ) == '__frontend__'
            ):
                initializer = self._aggregate_constant(symbol.type_spec, value)
            else:
                initializer = constant_value(
                    symbol.type_spec,
                    value,
                    self.type_registry,
                )
            if initializer.type != destination.type.pointee:
                raise GlobalEmissionError(
                    f'El inicializador de {symbol.name} no coincide con su tipo LLVM'
                )
            destination.initializer = initializer
        except LLVMTypeError as error:
            raise GlobalEmissionError(f'{symbol.name}: {error}') from error

    def emit_symbol(self, storage: Storage, symbol: Variable) -> None:
        """Emit one symbol for callers that use the emitter incrementally."""
        self._declare_symbol(storage, symbol)
        self._initialize_symbol(storage, symbol)

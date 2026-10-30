from __future__ import annotations

from dataclasses import dataclass

from llvmlite import ir

from core.frontend.objects import TypeSpec
from core.frontend.tools.types import (
    MAGIC_BINARY_OPERATORS,
    MAGIC_UNARY_OPERATORS,
)

from ..errors import FunctionEmissionError


class _VolatileLoadInstr(ir.instructions.LoadInstr):
    """llvmlite 0.50 lacks a public volatile-load builder API."""

    def descr(self, buf):
        [value] = self.operands
        align = f', align {self.align}' if self.align is not None else ''
        buf.append(
            f'load volatile {self.type}, {value.type} {value.get_reference()}'
            f'{align}{self._stringify_metadata(leading_comma=True)}\n'
        )

class _VolatileStoreInstr(ir.instructions.StoreInstr):
    """Counterpart to ``_VolatileLoadInstr`` for type-level volatile data."""

    def descr(self, buf):
        value, pointer = self.operands
        align = f', align {self.align}' if self.align is not None else ''
        buf.append(
            f'store volatile {value.type} {value.get_reference()}, '
            f'{pointer.type} {pointer.get_reference()}{align}'
            f'{self._stringify_metadata(leading_comma=True)}\n'
        )

@dataclass
class _MemoryPlace:
    address: ir.Value
    value_type: ir.Type
    alignment: int | None = None
    volatile: bool = False
    after_hooks: tuple[tuple[str, ir.Value, str], ...] = ()

@dataclass
class _BitfieldPlace:
    address: ir.Value
    field_type: ir.IntType
    backing_type: ir.IntType
    offset: int
    alignment: int | None = None
    volatile: bool = False
    unsigned: bool = False


class MemoryExpressionMixin:
    def _size_integer_type(self) -> ir.IntType:
        return ir.IntType(self._pointer_size * 8)

    @staticmethod
    def _is_array_descriptor_type(value_type: ir.Type) -> bool:
        elements = getattr(value_type, 'elements', ())
        return (
            isinstance(value_type, ir.LiteralStructType)
            and len(elements) == 2
            and isinstance(elements[0], ir.PointerType)
            and isinstance(elements[0].pointee, ir.IntType)
            and elements[0].pointee.width == 8
            and isinstance(elements[1], ir.IntType)
            and elements[1].width == 32
        )

    @staticmethod
    def _identified_name(value_type: ir.Type) -> str | None:
        return (
            value_type.name
            if isinstance(value_type, ir.IdentifiedStructType)
            else None
        )

    def _aggregate_volatile(self, value_type: ir.Type) -> bool:
        name = self._identified_name(value_type)
        return bool(
            name
            and self.type_registry is not None
            and self.type_registry.is_volatile(name)
        )

    def _place_alignment(
        self,
        value_type: ir.Type,
        fallback: int | None = None,
    ) -> int | None:
        if fallback is not None:
            return fallback
        if self.type_registry is not None:
            return self.type_registry.abi_alignment(value_type)
        return None

    def _access_hooks_enabled(self) -> bool:
        """Return whether compiler-generated class hooks are active here."""
        symbol = self._active_function_symbol
        return (
            not self._suppress_magic_hooks
            and (symbol is None or not getattr(symbol, 'is_method', False))
        )

    def _emit_member_access_hook(
        self,
        type_name: str,
        place: _MemoryPlace,
        member_name: str,
        hook_mode: str,
        builder: ir.IRBuilder,
    ) -> tuple[str, ir.Value, str] | None:
        if hook_mode not in {'read', 'write'} or self.type_registry is None:
            return None
        aggregate = self.type_registry.aggregate(type_name)
        if aggregate is None or not getattr(aggregate, 'is_class', False):
            return None
        method_name = (
            '__onsetter__'
            if hook_mode == 'write'
            else '__ongetter__'
        )
        method = self._resolve_method_symbol(type_name, method_name)
        if method is None or not self._access_hooks_enabled():
            return None
        if 'after' in getattr(method, 'decorators', ()):
            return (type_name, place.address, member_name)
        self._emit_magic_method_call(
            type_name,
            place.address,
            method_name,
            builder,
            attribute_name=member_name,
        )
        return None

    def _emit_after_access_hooks(
        self,
        hooks: tuple[tuple[str, ir.Value, str], ...],
        builder: ir.IRBuilder,
        *,
        hook_mode: str,
    ) -> None:
        method_name = (
            '__onsetter__'
            if hook_mode == 'write'
            else '__ongetter__'
        )
        for type_name, receiver_address, member_name in reversed(hooks):
            self._emit_magic_method_call(
                type_name,
                receiver_address,
                method_name,
                builder,
                attribute_name=member_name,
            )

    def _method_receiver_address(
        self,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        symbol = self._active_function_symbol
        receiver_name = getattr(symbol, 'receiver_name', None)
        if (
            symbol is None
            or not symbol.is_method
            or symbol.is_static
            or not receiver_name
        ):
            raise FunctionEmissionError(
                'El metodo actual no tiene un receptor de instancia'
            )
        receiver_slot = values.get(receiver_name)
        if receiver_slot is None:
            raise FunctionEmissionError(
                f'El receptor {receiver_name} no tiene almacenamiento LLVM'
            )
        receiver = self._load_place(
            self._memory_place(
                receiver_slot,
                alignment=getattr(receiver_slot, 'align', None),
            ),
            builder,
        )
        return self._checked_pointer(receiver, builder)

    def _method_self_place(
        self,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> _MemoryPlace | None:
        symbol = self._active_function_symbol
        if (
            symbol is None
            or not symbol.is_method
            or symbol.is_static
            or not symbol.owner_type
            or self.type_registry is None
        ):
            return None
        layout = self.type_registry.layout(symbol.owner_type)
        receiver = self._method_receiver_address(builder, values)
        alignment = None
        if layout is not None:
            alignment = 1 if layout.symbol.is_packed else layout.alignment
        return self._memory_place(
            receiver,
            alignment=alignment,
            volatile=bool(layout and layout.symbol.is_volatile),
        )

    def _memory_place(
        self,
        address: ir.Value,
        *,
        alignment: int | None = None,
        volatile: bool = False,
        after_hooks: tuple[tuple[str, ir.Value, str], ...] = (),
    ) -> _MemoryPlace:
        if not isinstance(address.type, ir.PointerType):
            raise FunctionEmissionError('La expresion no tiene direccion LLVM')
        value_type = address.type.pointee
        return _MemoryPlace(
            address=address,
            value_type=value_type,
            alignment=self._place_alignment(value_type, alignment),
            volatile=volatile or self._aggregate_volatile(value_type),
            after_hooks=after_hooks,
        )

    def _load_address(
        self,
        address: ir.Value,
        builder: ir.IRBuilder,
        *,
        alignment: int | None = None,
        volatile: bool = False,
        name: str = '',
    ) -> ir.Value:
        if volatile:
            instruction = _VolatileLoadInstr(builder.block, address, name=name)
            instruction.align = alignment
            builder._insert(instruction)
            return instruction
        return builder.load(address, name=name, align=alignment)

    def _store_address(
        self,
        value: ir.Value,
        address: ir.Value,
        builder: ir.IRBuilder,
        *,
        alignment: int | None = None,
        volatile: bool = False,
    ) -> None:
        if volatile:
            instruction = _VolatileStoreInstr(builder.block, value, address)
            instruction.align = alignment
            builder._insert(instruction)
            return
        builder.store(value, address, align=alignment)

    def _load_place(
        self,
        place: _MemoryPlace | _BitfieldPlace,
        builder: ir.IRBuilder,
    ) -> ir.Value:
        if isinstance(place, _MemoryPlace):
            return self._load_address(
                place.address,
                builder,
                alignment=place.alignment,
                volatile=place.volatile,
            )
        stored = self._load_address(
            place.address,
            builder,
            alignment=place.alignment,
            volatile=place.volatile,
        )
        shifted = builder.lshr(
            stored,
            ir.Constant(place.backing_type, place.offset),
        )
        mask = (1 << place.field_type.width) - 1
        masked = builder.and_(shifted, ir.Constant(place.backing_type, mask))
        if place.field_type.width == place.backing_type.width:
            return masked
        return builder.trunc(masked, place.field_type)

    def _store_place(
        self,
        value: ir.Value,
        place: _MemoryPlace | _BitfieldPlace,
        builder: ir.IRBuilder,
    ) -> None:
        if isinstance(place, _MemoryPlace):
            self._store_address(
                value,
                place.address,
                builder,
                alignment=place.alignment,
                volatile=place.volatile,
            )
            return

        field_value = self._coerce_value(value, place.field_type, builder)
        if place.field_type.width < place.backing_type.width:
            field_value = builder.zext(field_value, place.backing_type)
        mask = (1 << place.field_type.width) - 1
        placed_mask = mask << place.offset
        current = self._load_address(
            place.address,
            builder,
            alignment=place.alignment,
            volatile=place.volatile,
        )
        cleared = builder.and_(
            current,
            ir.Constant(place.backing_type, ~placed_mask),
        )
        inserted = builder.shl(
            builder.and_(field_value, ir.Constant(place.backing_type, mask)),
            ir.Constant(place.backing_type, place.offset),
        )
        self._store_address(
            builder.or_(cleared, inserted),
            place.address,
            builder,
            alignment=place.alignment,
            volatile=place.volatile,
        )

    def _buffer_data_and_length(
        self,
        descriptor: ir.Value,
        builder: ir.IRBuilder,
    ) -> tuple[ir.Value, ir.Value]:
        if not self._is_buffer_descriptor_type(descriptor.type):
            raise FunctionEmissionError(
                'El valor no tiene el descriptor LLVM de buffer'
            )
        return (
            builder.extract_value(descriptor, 0, name='buffer.data'),
            builder.extract_value(descriptor, 1, name='buffer.len'),
        )

    def _emit_buffer_bounds_check(
        self,
        index: ir.Value,
        length: ir.Value,
        builder: ir.IRBuilder,
    ) -> None:
        if index.type != length.type:
            raise FunctionEmissionError(
                'El indice y la capacidad del buffer tienen anchos distintos'
            )
        function = builder.function
        if function is None:
            raise FunctionEmissionError(
                'La comprobacion de limites del buffer requiere una funcion'
            )
        block_id = len(function.blocks)
        valid_block = function.append_basic_block(
            name=f'buffer.index.valid.{block_id}'
        )
        invalid_block = function.append_basic_block(
            name=f'buffer.index.invalid.{block_id}'
        )
        valid = builder.icmp_unsigned('<', index, length)
        builder.cbranch(valid, valid_block, invalid_block)

        invalid_builder = ir.IRBuilder(invalid_block)
        self._emit_trap(invalid_builder)
        builder.position_at_end(valid_block)

    def _emit_buffer_concat(
        self,
        left: ir.Value,
        right: ir.Value,
        builder: ir.IRBuilder,
    ) -> ir.Value:
        left_data, left_length = self._buffer_data_and_length(left, builder)
        right_data, right_length = self._buffer_data_and_length(right, builder)
        size_type = self._size_integer_type()
        total = builder.add(left_length, right_length, name='buffer.total')
        byte_pointer = ir.IntType(8).as_pointer()
        malloc = self._runtime_function(
            'malloc',
            byte_pointer,
            [size_type],
        )
        data = builder.call(malloc, [total], name='buffer.concat.data')
        is_null = builder.icmp_unsigned(
            '==',
            data,
            ir.Constant(byte_pointer, None),
        )
        function = builder.function
        if function is None:
            raise FunctionEmissionError(
                'La concatenacion de buffer requiere una funcion'
            )
        block_id = len(function.blocks)
        ok_block = function.append_basic_block(
            name=f'buffer.concat.ok.{block_id}'
        )
        fail_block = function.append_basic_block(
            name=f'buffer.concat.fail.{block_id}'
        )
        builder.cbranch(is_null, fail_block, ok_block)
        fail_builder = ir.IRBuilder(fail_block)
        self._emit_trap(fail_builder)
        builder.position_at_end(ok_block)

        memcpy = self._runtime_function(
            'memcpy',
            byte_pointer,
            [byte_pointer, byte_pointer, size_type],
        )
        builder.call(memcpy, [data, left_data, left_length])
        right_destination = builder.gep(data, [left_length], inbounds=False)
        builder.call(memcpy, [right_destination, right_data, right_length])

        descriptor_type = left.type
        descriptor = ir.Constant(descriptor_type, None)
        descriptor = builder.insert_value(descriptor, data, 0)
        return builder.insert_value(descriptor, total, 1)

    def _compile_place(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
        *,
        hook_mode: str = 'none',
    ) -> _MemoryPlace | _BitfieldPlace:
        """Resolve an assignable LLVM place, including union/bitfield views."""
        current = node
        while (
            getattr(current, 'name', None) in {'VALUE', 'PRIMARY'}
            and len(self._children(current)) == 1
        ):
            current = self._children(current)[0]

        if getattr(current, 'name', None) == 'ASSIGN_TARGET':
            children = self._children(current)
            if not children:
                raise FunctionEmissionError('El destino no tiene una expresion')
            return self._compile_place(
                children[0],
                builder,
                values,
                hook_mode=hook_mode,
            )

        if getattr(current, 'name', None) == 'PAREN_VALUE':
            inner = next(
                (
                    child for child in self._children(current)
                    if getattr(child, 'name', None) == 'VALUE'
                ),
                None,
            )
            if inner is None:
                raise FunctionEmissionError('La expresion parentizada esta vacia')
            value = self._compile_expression(inner, builder, values)
            if isinstance(value.type, ir.PointerType):
                return self._memory_place(
                    self._checked_pointer(value, builder),
                    alignment=1,
                )
            return self._compile_place(
                inner,
                builder,
                values,
                hook_mode=hook_mode,
            )

        if getattr(current, 'name', None) == 'DEREF_TARGET':
            children = self._children(current)
            if not children:
                raise FunctionEmissionError('La desreferenciacion esta vacia')
            value = self._compile_expression(children[0], builder, values)
            if not isinstance(value.type, ir.PointerType):
                raise FunctionEmissionError('La desreferenciacion requiere un puntero')
            return self._memory_place(
                self._checked_pointer(value, builder),
                alignment=1,
            )

        if getattr(current, 'name', None) == 'DEREF_ASSIGN_TARGET':
            children = self._children(current)
            if not children:
                raise FunctionEmissionError('La desreferenciacion esta vacia')
            value = self._compile_expression(children[0], builder, values)
            if not isinstance(value.type, ir.PointerType):
                raise FunctionEmissionError('La desreferenciacion requiere un puntero')
            return self._memory_place(
                self._checked_pointer(value, builder),
                alignment=1,
            )

        if getattr(current, 'name', None) == 'POSTFIX_EXPR':
            children = self._children(current)
            primary = children[0] if children else None
            suffixes: list[object] = []
            for child in children[1:]:
                suffixes.extend(
                    self._children(child) if isinstance(child, list) else [child]
                )
            if primary is None:
                raise FunctionEmissionError('El acceso no tiene una base')

            place = self._compile_place(primary, builder, values)
            for suffix_index, suffix in enumerate(suffixes):
                if isinstance(place, _BitfieldPlace):
                    raise FunctionEmissionError(
                        'Un campo de flags no admite accesos posteriores'
                    )
                name = getattr(suffix, 'name', None)
                if name == 'CALL_SUFFIX':
                    raise FunctionEmissionError(
                        'Una llamada no puede usarse como destino de asignacion'
                    )
                if name == 'INDEX_ACCESS':
                    index_node = next(
                        (
                            child for child in self._children(suffix)
                            if getattr(child, 'name', None) == 'VALUE'
                        ),
                        None,
                    )
                    if index_node is None:
                        raise FunctionEmissionError('El indice no contiene una expresion')
                    index_type = self._size_integer_type()
                    index = self._coerce_value(
                        self._compile_expression(index_node, builder, values),
                        index_type,
                        builder,
                        signed=False,
                    )
                    zero_index = ir.Constant(index_type, 0)
                    address = place.address
                    pointee = place.value_type
                    if self._is_array_descriptor_type(pointee):
                        descriptor = self._load_place(place, builder)
                        data = builder.extract_value(descriptor, 0)
                        place = self._memory_place(
                            builder.gep(data, [index], inbounds=False),
                            alignment=1,
                            volatile=place.volatile,
                            after_hooks=place.after_hooks,
                        )
                    elif self._is_buffer_descriptor_type(pointee):
                        descriptor = self._load_place(place, builder)
                        data, length = self._buffer_data_and_length(
                            descriptor,
                            builder,
                        )
                        self._emit_buffer_bounds_check(index, length, builder)
                        place = self._memory_place(
                            builder.gep(data, [index], inbounds=False),
                            alignment=1,
                            volatile=place.volatile,
                            after_hooks=place.after_hooks,
                        )
                    elif isinstance(pointee, ir.PointerType):
                        address = self._checked_pointer(
                            self._load_place(place, builder),
                            builder,
                        )
                        if isinstance(address.type.pointee, ir.ArrayType):
                            address = builder.gep(
                                address,
                                [zero_index, index],
                                inbounds=False,
                            )
                        else:
                            address = builder.gep(
                                address,
                                [index],
                                inbounds=False,
                            )
                        place = self._memory_place(
                            address,
                            alignment=1,
                            after_hooks=place.after_hooks,
                        )
                    elif isinstance(pointee, ir.ArrayType):
                        address = builder.gep(
                            address,
                            [zero_index, index],
                            inbounds=False,
                        )
                        element_alignment = (
                            1 if place.alignment == 1
                            else self._place_alignment(pointee.element)
                        )
                        place = self._memory_place(
                            address,
                            alignment=element_alignment,
                            volatile=place.volatile,
                            after_hooks=place.after_hooks,
                        )
                    else:
                        # The semantic pass guarantees that this is a pointer
                        # access.  A scalar GEP keeps raw-pointer indexing
                        # available for future pointer arithmetic without
                        # inventing a second address representation.
                        place = self._memory_place(
                            builder.gep(address, [index], inbounds=False),
                            alignment=1,
                            after_hooks=place.after_hooks,
                        )
                    continue
                if name == 'MEMBER_ACCESS':
                    member = self._identifier(suffix)
                    pointee = place.value_type
                    type_name = self._identified_name(pointee)
                    if type_name is None or self.type_registry is None:
                        raise FunctionEmissionError(
                            'El acceso a miembros requiere un struct LLVM'
                        )
                    layout = self.type_registry.layout(type_name)
                    field = self.type_registry.field_spec(type_name, member or '')
                    if layout is None or field is None:
                        raise FunctionEmissionError(
                            f'El miembro {member or "<anonimo>"} no existe en '
                            f'{type_name}'
                        )
                    volatile = place.volatile or layout.symbol.is_volatile
                    if layout.symbol.kind == 'flags':
                        if suffix_index != len(suffixes) - 1:
                            raise FunctionEmissionError(
                                'Un campo de flags debe ser el acceso final'
                            )
                        path = layout.storage_path
                        backing = layout.backing_type
                        field_type = self.type_registry.resolve(field.type_spec)
                        if (
                            path is None
                            or not isinstance(backing, ir.IntType)
                            or not isinstance(field_type, ir.IntType)
                            or field.bit_offset is None
                        ):
                            raise FunctionEmissionError(
                                f'El campo de flags {type_name}.{member} no tiene layout LLVM'
                            )
                        storage = builder.gep(
                            place.address,
                            [ir.Constant(ir.IntType(32), 0), *(
                                ir.Constant(ir.IntType(32), item) for item in path
                            )],
                            inbounds=False,
                        )
                        alignment = 1 if layout.symbol.is_packed else min(
                            place.alignment or layout.alignment,
                            self._place_alignment(backing) or 1,
                        )
                        place = _BitfieldPlace(
                            address=storage,
                            field_type=field_type,
                            backing_type=backing,
                            offset=field.bit_offset,
                            alignment=alignment,
                            volatile=volatile,
                            unsigned=(
                                field.type_spec.name.startswith('u')
                                or field.type_spec.name == 'byte'
                            ),
                        )
                        continue

                    field_type = self.type_registry.resolve(field.type_spec)
                    if layout.symbol.kind == 'mold':
                        path = layout.storage_path
                        if path is None:
                            raise FunctionEmissionError(
                                f'El mold {type_name} no tiene almacenamiento LLVM'
                            )
                        storage = builder.gep(
                            place.address,
                            [ir.Constant(ir.IntType(32), 0), *(
                                ir.Constant(ir.IntType(32), item) for item in path
                            )],
                            inbounds=False,
                        )
                        address = builder.bitcast(storage, field_type.as_pointer())
                    else:
                        path = self.type_registry.field_path(type_name, member or '')
                        if path is None:
                            raise FunctionEmissionError(
                                f'El miembro {member or "<anonimo>"} no tiene ruta LLVM'
                            )
                        address = builder.gep(
                            place.address,
                            [ir.Constant(ir.IntType(32), 0), *(
                                ir.Constant(ir.IntType(32), item) for item in path
                            )],
                            inbounds=False,
                        )
                    member_hook_mode = hook_mode
                    if (
                        hook_mode == 'write'
                        and suffix_index != len(suffixes) - 1
                    ):
                        member_hook_mode = 'read'
                    after_hook = self._emit_member_access_hook(
                        type_name,
                        place,
                        member or '',
                        member_hook_mode,
                        builder,
                    )
                    after_hooks = place.after_hooks
                    if after_hook is not None:
                        after_hooks = (*after_hooks, after_hook)
                    alignment = 1 if layout.symbol.is_packed else min(
                        place.alignment or layout.alignment,
                        self._place_alignment(field_type) or 1,
                    )
                    place = self._memory_place(
                        address,
                        alignment=alignment,
                        volatile=volatile,
                        after_hooks=after_hooks,
                    )
            return place

        kind = self._token_kind(current)
        value = self._token_value(current)
        if kind == 'IDENT':
            name = str(value)
            if name in values:
                address = values[name]
                return self._memory_place(
                    address,
                    alignment=getattr(address, 'align', None),
                )
            if name == 'self':
                self_place = self._method_self_place(builder, values)
                if self_place is not None:
                    return self_place
            global_value = self.module.globals.get(self._global_llvm_name(name))
            if isinstance(global_value, ir.GlobalVariable):
                return self._memory_place(
                    global_value,
                    alignment=getattr(global_value, 'align', None),
                )
            raise FunctionEmissionError(
                f'La variable {name} no tiene almacenamiento LLVM'
            )

        raise FunctionEmissionError('La expresion no es direccionable')

    def _compile_address(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
        *,
        hook_mode: str = 'none',
    ) -> ir.Value:
        place = self._compile_place(
            node,
            builder,
            values,
            hook_mode=hook_mode,
        )
        if isinstance(place, _BitfieldPlace):
            raise FunctionEmissionError(
                'Un campo de flags no tiene una direccion independiente'
            )
        if place.after_hooks:
            self._emit_after_access_hooks(
                place.after_hooks,
                builder,
                hook_mode=hook_mode,
            )
        return place.address

    def _is_static_global_chain(
        self,
        name: str,
        value: ir.Value,
    ) -> bool:
        """Allow pointer decay only for immutable, compile-time chains."""
        if not isinstance(value, ir.GlobalVariable):
            return False
        if not getattr(value, 'global_constant', False):
            return False

        pointee = value.type.pointee
        if not (
            isinstance(pointee, ir.ArrayType)
            and isinstance(pointee.element, ir.IntType)
            and pointee.element.width == 8
        ):
            return False

        info = self._global_values.get(name)
        type_spec = getattr(info, 'type_spec', None)
        return bool(
            info is not None
            and getattr(info, 'is_literal', False)
            and isinstance(getattr(info, 'value', None), str)
            and getattr(type_spec, 'name', None) == 'chain'
            and getattr(type_spec, 'pointer_level', 0) == 0
            and getattr(type_spec, 'array_depth', 0) == 0
        )

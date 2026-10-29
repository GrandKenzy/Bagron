from __future__ import annotations

from dataclasses import dataclass

from llvmlite import ir

from core.frontend.objects import TypeSpec
from core.frontend.tools.types import (
    MAGIC_BINARY_OPERATORS,
    MAGIC_UNARY_OPERATORS,
)

from .errors import FunctionEmissionError


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


class ExpressionEmitterMixin:
    """LLVM emission for expressions, aggregate places, and calls."""

    def _size_integer_type(self) -> ir.IntType:
        return ir.IntType(self._pointer_size * 8)

    @staticmethod
    def _integer_constant_value(value: ir.Value) -> int | None:
        if not isinstance(value, ir.Constant) or not isinstance(value.type, ir.IntType):
            return None
        constant = getattr(value, 'constant', None)
        return constant if isinstance(constant, int) else None

    @staticmethod
    def _integer_fits(value: int, target: ir.IntType, unsigned: bool) -> bool:
        if unsigned:
            return 0 <= value <= (1 << target.width) - 1
        return -(1 << (target.width - 1)) <= value <= (1 << (target.width - 1)) - 1

    def _integer_common_type(
        self,
        left: ir.Value,
        right: ir.Value,
        left_node: object,
        right_node: object,
        unsigned: bool,
    ) -> ir.IntType:
        if not isinstance(left.type, ir.IntType) or not isinstance(right.type, ir.IntType):
            raise FunctionEmissionError('Los operandos deben ser enteros en LLVM')
        left_value = self._integer_constant_value(left)
        right_value = self._integer_constant_value(right)
        if left_value is not None and self._integer_fits(
            left_value,
            right.type,
            self._expression_is_unsigned(right_node),
        ):
            return right.type
        if right_value is not None and self._integer_fits(
            right_value,
            left.type,
            self._expression_is_unsigned(left_node),
        ):
            return left.type
        return left.type if left.type.width >= right.type.width else right.type

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

    def _emit_magic_method_call(
        self,
        owner_type: str,
        receiver_address: ir.Value,
        method_name: str,
        builder: ir.IRBuilder,
        *,
        attribute_name: str | None = None,
    ) -> ir.Value | None:
        """Emit one optional magic-method call for an external access.

        Access hooks are ordinary instance methods.  The compiler only
        synthesizes their arguments and never exposes a second runtime
        dispatch mechanism.  A status hook must return exactly ``1`` to allow
        the access; ``0`` (or another value) traps before the access proceeds.
        """
        if not self._access_hooks_enabled() or self.type_registry is None:
            return None

        method = self._resolve_method_symbol(owner_type, method_name)
        if method is None:
            return None
        callee = self._functions.get(method.name)
        if callee is None:
            raise FunctionEmissionError(
                f'El metodo magico {method.name} no tiene emision LLVM'
            )
        if not isinstance(receiver_address.type, ir.PointerType):
            raise FunctionEmissionError(
                f'El receptor de {owner_type}.{method_name} no es direccionable'
            )

        arguments: list[ir.Value] = []
        llvm_index = 0
        for parameter in method.signature.parameters:
            if llvm_index >= len(callee.args):
                raise FunctionEmissionError(
                    f'La firma de {method.name} no coincide con su ABI LLVM'
                )
            target_type = callee.args[llvm_index].type
            if parameter.is_receiver:
                argument = self._coerce_value(
                    receiver_address,
                    target_type,
                    builder,
                )
            elif parameter.is_length:
                if attribute_name is None:
                    raise FunctionEmissionError(
                        f'{method.name} requiere un atributo para Len_t'
                    )
                try:
                    length = len(attribute_name.encode('ascii')) + 1
                except UnicodeEncodeError as error:
                    raise FunctionEmissionError(
                        'El nombre de un atributo usado por un metodo magico '
                        'solo puede contener ASCII'
                    ) from error
                argument = self._coerce_value(
                    ir.Constant(self._size_integer_type(), length),
                    target_type,
                    builder,
                    signed=False,
                )
            else:
                if attribute_name is None:
                    raise FunctionEmissionError(
                        f'La firma de {method.name} contiene parametros no '
                        'soportados por el compilador'
                    )
                argument = self._coerce_value(
                    self._string_pointer(attribute_name, builder),
                    target_type,
                    builder,
                )
            arguments.append(argument)
            llvm_index += 1

        result = builder.call(callee, arguments)
        if method_name not in {'__ongetter__', '__onsetter__'}:
            return result

        if not isinstance(result.type, ir.IntType):
            raise FunctionEmissionError(
                f'El metodo magico {method.name} debe retornar un entero de '
                'estado'
            )
        allowed = (
            result
            if result.type.width == 1
            else builder.icmp_unsigned(
                '==',
                result,
                ir.Constant(result.type, 1),
            )
        )
        function = builder.function
        if function is None:
            raise FunctionEmissionError(
                f'El metodo magico {method.name} no esta dentro de una funcion'
            )
        block_id = len(function.blocks)
        allowed_block = function.append_basic_block(
            name=f'{method_name[2:-2]}.allowed.{block_id}'
        )
        denied_block = function.append_basic_block(
            name=f'{method_name[2:-2]}.denied.{block_id}'
        )
        builder.cbranch(allowed, allowed_block, denied_block)

        denied_builder = ir.IRBuilder(denied_block)
        trap = self.module.globals.get('llvm.trap')
        if trap is None:
            trap = ir.Function(
                self.module,
                ir.FunctionType(ir.VoidType(), []),
                name='llvm.trap',
            )
        denied_builder.call(trap, [])
        denied_builder.unreachable()
        builder.position_at_end(allowed_block)
        return None

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
                    index = self._coerce_value(
                        self._compile_expression(index_node, builder, values),
                        ir.IntType(32),
                        builder,
                        signed=False,
                    )
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
                    elif isinstance(pointee, ir.PointerType):
                        address = self._checked_pointer(
                            self._load_place(place, builder),
                            builder,
                        )
                        if isinstance(address.type.pointee, ir.ArrayType):
                            address = builder.gep(
                                address,
                                [ir.Constant(ir.IntType(32), 0), index],
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
                            [ir.Constant(ir.IntType(32), 0), index],
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
            global_value = self.module.globals.get(name)
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

    def _compile_expression(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
        expected_type: ir.Type | None = None,
    ) -> ir.Value:
        current = self._unwrap(node)

        if getattr(current, 'name', None) == 'LOGICAL_NOT':
            operand_node = next(
                (
                    child for child in self._children(current)
                    if getattr(child, 'name', None) is not None
                ),
                None,
            )
            if operand_node is None:
                raise FunctionEmissionError(
                    'La negacion logica requiere un operando'
                )
            operand = self._compile_expression(
                operand_node,
                builder,
                values,
            )
            operand = self._coerce_condition_value(operand, builder)
            return builder.xor(operand, ir.Constant(ir.IntType(1), 1))

        if type(current).__name__ == 'ASTUnaryOp':
            operator = getattr(
                getattr(current.operator, 'token', None),
                'name',
                None,
            )
            magic_result = self._compile_magic_operator(
                current,
                operator,
                builder,
                values,
            )
            if magic_result is not None:
                return magic_result
            if operator == 'DOLLAR':
                return self._compile_address(current.operand, builder, values)

            operand = self._compile_expression(current.operand, builder, values)
            if operator == 'PLUS':
                return operand
            if operator == 'MINUS':
                return (
                    builder.fneg(operand)
                    if self._is_float_type(operand.type)
                    else builder.neg(operand)
                )
            if operator in {'NOT_LOGIC', 'LOGIC_NOT', 'EXCLAMATION'}:
                operand = self._coerce_condition_value(operand, builder)
                return builder.xor(operand, ir.Constant(ir.IntType(1), 1))
            raise FunctionEmissionError(
                f'Operador unario no soportado en LLVM: {operator}'
            )

        if type(current).__name__ == 'ASTBinaryOp':
            operator = getattr(
                getattr(current.operator, 'token', None),
                'name',
                None,
            )
            magic_result = self._compile_magic_operator(
                current,
                operator,
                builder,
                values,
            )
            if magic_result is not None:
                return magic_result
            left = self._compile_expression(current.left, builder, values)
            right = self._compile_expression(current.right, builder, values)
            unsigned = (
                self._expression_is_unsigned(current.left)
                or self._expression_is_unsigned(current.right)
            )

            if operator in {
                'AND_LOGIC',
                'LOGIC_AND',
                'OR_LOGIC',
                'LOGIC_OR',
            }:
                left = self._coerce_condition_value(left, builder)
                right = self._coerce_condition_value(right, builder)
                return (
                    builder.and_(left, right)
                    if operator in {'AND_LOGIC', 'LOGIC_AND'}
                    else builder.or_(left, right)
                )

            left_is_float = self._is_float_type(left.type)
            right_is_float = self._is_float_type(right.type)
            if left.type != right.type:
                if left_is_float and right_is_float:
                    target_type = (
                        left.type
                        if self._float_rank(left.type) >= self._float_rank(right.type)
                        else right.type
                    )
                    left = self._coerce_value(left, target_type, builder)
                    right = self._coerce_value(right, target_type, builder)
                elif left_is_float:
                    right = self._coerce_value(
                        right,
                        left.type,
                        builder,
                        signed=not unsigned,
                    )
                elif right_is_float:
                    left = self._coerce_value(
                        left,
                        right.type,
                        builder,
                        signed=not unsigned,
                    )
                elif isinstance(left.type, ir.IntType) and isinstance(
                    right.type,
                    ir.IntType,
                ):
                    target_type = self._integer_common_type(
                        left,
                        right,
                        current.left,
                        current.right,
                        unsigned,
                    )
                    left = self._coerce_int(
                        left,
                        target_type,
                        builder,
                        signed=not unsigned,
                    )
                    right = self._coerce_int(
                        right,
                        target_type,
                        builder,
                        signed=not unsigned,
                    )
                else:
                    raise FunctionEmissionError(
                        'Los operandos aritmeticos deben ser enteros o flotantes'
                    )

            if operator in {
                'EQUAL',
                'NOT_EQUAL',
                'LESS',
                'LESS_EQUAL',
                'GREATER',
                'GREATER_EQUAL',
            }:
                predicates = {
                    'EQUAL': '==',
                    'NOT_EQUAL': '!=',
                    'LESS': '<',
                    'LESS_EQUAL': '<=',
                    'GREATER': '>',
                    'GREATER_EQUAL': '>=',
                }
                if self._is_float_type(left.type):
                    if operator == 'NOT_EQUAL':
                        return builder.fcmp_unordered(
                            predicates[operator],
                            left,
                            right,
                        )
                    return builder.fcmp_ordered(
                        predicates[operator],
                        left,
                        right,
                    )
                compare = (
                    builder.icmp_unsigned
                    if unsigned
                    else builder.icmp_signed
                )
                return compare(predicates[operator], left, right)

            if self._is_float_type(left.type):
                operations = {
                    'PLUS': builder.fadd,
                    'MINUS': builder.fsub,
                    'STAR': builder.fmul,
                    'SLASH': builder.fdiv,
                    'PERCENT': builder.frem,
                }
            else:
                operations = {
                    'PLUS': builder.add,
                    'MINUS': builder.sub,
                    'STAR': builder.mul,
                    'SLASH': builder.udiv if unsigned else builder.sdiv,
                    'PERCENT': builder.urem if unsigned else builder.srem,
                    'AND': builder.and_,
                    'OR': builder.or_,
                    'XOR': builder.xor,
                    'SHL': builder.shl,
                    'SHR': builder.lshr if unsigned else builder.ashr,
                }
            operation = operations.get(operator)
            if operation is None:
                raise FunctionEmissionError(
                    f'Operador no soportado en LLVM: {operator}'
                )
            return operation(left, right)

        if getattr(current, 'name', None) == 'POSTFIX_EXPR':
            children = self._children(current)
            primary = children[0] if children else None
            suffixes: list[object] = []
            for child in children[1:]:
                suffixes.extend(
                    self._children(child) if isinstance(child, list) else [child]
                )
            call_suffix = next(
                (
                    suffix for suffix in suffixes
                    if getattr(suffix, 'name', None) == 'CALL_SUFFIX'
                ),
                None,
            )
            if call_suffix is not None:
                return self._compile_call(current, builder, values)
            if primary is not None and not suffixes:
                return self._compile_expression(primary, builder, values)
            if primary is not None:
                member_suffix = next(
                    (
                        suffix for suffix in suffixes
                        if getattr(suffix, 'name', None) == 'MEMBER_ACCESS'
                        and self._identifier(suffix) == 'len'
                    ),
                    None,
                )
                if member_suffix is not None and len(suffixes) == 1:
                    address = self._compile_address(
                        primary,
                        builder,
                        values,
                        hook_mode='read',
                    )
                    pointee = address.type.pointee
                    if isinstance(pointee, ir.ArrayType):
                        return ir.Constant(self._size_integer_type(), pointee.count)
                    if self._is_array_descriptor_type(pointee):
                        descriptor = builder.load(address)
                        return builder.extract_value(descriptor, 1)
                    raise FunctionEmissionError(
                        'La longitud solo puede obtenerse de un array'
                    )
                place = self._compile_place(
                    current,
                    builder,
                    values,
                    hook_mode='read',
                )
                result = self._load_place(place, builder)
                if isinstance(place, _MemoryPlace) and place.after_hooks:
                    self._emit_after_access_hooks(
                        place.after_hooks,
                        builder,
                        hook_mode='read',
                    )
                return result

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
                return self._load_address(
                    self._checked_pointer(value, builder),
                    builder,
                    alignment=1,
                )
            return value

        if getattr(current, 'name', None) in {'VALUE', 'PRIMARY'}:
            children = self._children(current)
            if len(children) == 1:
                return self._compile_expression(children[0], builder, values)

        kind = self._token_kind(current)
        value = self._token_value(current)
        if kind in {'NUMBER', 'DECIMAL'}:
            if self._is_float_type(expected_type) or kind == 'DECIMAL':
                target_type = (
                    expected_type
                    if self._is_float_type(expected_type)
                    else ir.FloatType()
                )
                return ir.Constant(target_type, float(value))
            return ir.Constant(ir.IntType(32), int(value))
        if kind == 'BOOL':
            return ir.Constant(ir.IntType(1), int(str(value).lower() == 'true'))
        if kind == 'NULL':
            return ir.Constant(ir.IntType(8).as_pointer(), None)
        if kind == 'STRING':
            if not isinstance(value, str):
                raise FunctionEmissionError('El literal de cadena no es valido')
            try:
                data = value.encode('ascii')
            except UnicodeEncodeError as error:
                raise FunctionEmissionError(
                    'Una cadena usada por la ABI actual solo puede contener ASCII'
                ) from error
            if isinstance(expected_type, ir.IntType) and expected_type.width == 8:
                if len(data) != 1:
                    raise FunctionEmissionError(
                        'Un literal usado como char o byte debe contener un byte'
                    )
                return ir.Constant(expected_type, data[0])
            return self._string_pointer(value, builder)
        if kind == 'IDENT':
            name = str(value)
            if name in values:
                result = values[name]
            else:
                if name == 'self':
                    self_place = self._method_self_place(builder, values)
                    if self_place is not None:
                        result = self._load_place(self_place, builder)
                    else:
                        result = None
                else:
                    result = None
                if result is None and name in self.module.globals:
                    result = self.module.globals[name]
                if result is None:
                    raise FunctionEmissionError(
                        f'La variable {name} no tiene emision LLVM en esta fase'
                    )
            active_spec = self._active_type_spec(name)
            chain_pointer = (
                isinstance(expected_type, ir.PointerType)
                and isinstance(expected_type.pointee, ir.IntType)
                and expected_type.pointee.width == 8
                and (
                    (
                        active_spec is not None
                        and active_spec.name == 'chain'
                    )
                    or self._is_static_global_chain(name, result)
                )
            )
            if chain_pointer:
                if isinstance(result, ir.GlobalVariable):
                    return builder.gep(
                        result,
                        [ir.Constant(ir.IntType(32), 0)] * 2,
                        inbounds=True,
                    )
                if getattr(result, 'opname', None) == 'alloca':
                    pointee = result.type.pointee
                    if isinstance(pointee, ir.PointerType):
                        return builder.load(result)
                    if isinstance(pointee, ir.ArrayType):
                        return builder.gep(
                            result,
                            [
                                ir.Constant(ir.IntType(32), 0),
                                ir.Constant(ir.IntType(32), 0),
                            ],
                            inbounds=True,
                        )
            if getattr(result, 'opname', None) == 'alloca':
                return self._load_place(
                    self._memory_place(
                        result,
                        alignment=getattr(result, 'align', None),
                    ),
                    builder,
                )
            if isinstance(result, ir.GlobalVariable):
                return self._load_place(
                    self._memory_place(
                        result,
                        alignment=getattr(result, 'align', None),
                    ),
                    builder,
                )
            return result

        raise FunctionEmissionError(
            'La expresion de retorno no tiene emision LLVM en esta fase'
        )

    def _class_expression_type_name(self, node: object) -> str | None:
        """Resolve the class type represented by a conditional expression."""
        if self.type_registry is None:
            return None

        current = self._unwrap(node)
        if getattr(current, 'name', None) == 'PAREN_VALUE':
            inner = next(
                (
                    child for child in self._children(current)
                    if getattr(child, 'name', None) == 'VALUE'
                ),
                None,
            )
            return self._class_expression_type_name(inner) if inner is not None else None

        if self._token_kind(current) == 'IDENT':
            spec = self._active_type_spec(str(self._token_value(current)))
            if (
                spec is not None
                and spec.pointer_level == 0
                and spec.array_depth == 0
            ):
                aggregate = self.type_registry.aggregate(spec.name)
                if aggregate is not None and getattr(aggregate, 'is_class', False):
                    return spec.name
            return None

        if getattr(current, 'name', None) != 'POSTFIX_EXPR':
            return None

        children = self._children(current)
        primary = children[0] if children else None
        suffixes: list[object] = []
        for child in children[1:]:
            suffixes.extend(
                self._children(child) if isinstance(child, list) else [child]
            )
        if primary is None:
            return None

        call_suffix = next(
            (
                suffix for suffix in suffixes
                if getattr(suffix, 'name', None) == 'CALL_SUFFIX'
            ),
            None,
        )
        if call_suffix is not None:
            constructor_name = self._call_name(primary, suffixes)
            aggregate = self.type_registry.aggregate(constructor_name or '')
            if aggregate is not None and getattr(aggregate, 'is_class', False):
                return aggregate.name
            method, _ = self._method_call_target(primary, suffixes)
            if method is None:
                return None
            return_type = getattr(method.signature, 'return_type', None)
            if return_type is None or return_type.pointer_level or return_type.array_depth:
                return None
            aggregate = self.type_registry.aggregate(return_type.name)
            return (
                return_type.name
                if aggregate is not None and getattr(aggregate, 'is_class', False)
                else None
            )

        type_name = self._class_expression_type_name(primary)
        if type_name is None:
            return None
        for suffix in suffixes:
            if getattr(suffix, 'name', None) != 'MEMBER_ACCESS':
                continue
            field = self.type_registry.field_spec(
                type_name,
                self._identifier(suffix) or '',
            )
            if field is None:
                return None
            field_type = field.type_spec
            if field_type.pointer_level or field_type.array_depth:
                return None
            aggregate = self.type_registry.aggregate(field_type.name)
            if aggregate is None or not getattr(aggregate, 'is_class', False):
                return None
            type_name = aggregate.name
        return type_name

    def _compile_class_receiver_address(
        self,
        node: object,
        type_name: str,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        """Get a pointer to a class expression for an implicit method call."""
        address_node = node
        while getattr(address_node, 'name', None) == 'PAREN_VALUE':
            inner = next(
                (
                    child for child in self._children(address_node)
                    if getattr(child, 'name', None) == 'VALUE'
                ),
                None,
            )
            if inner is None:
                break
            address_node = inner

        try:
            return self._compile_address(
                address_node,
                builder,
                values,
                hook_mode='read',
            )
        except FunctionEmissionError:
            value = self._compile_expression(node, builder, values)
            result_type_name = self._identified_name(value.type)
            if result_type_name != type_name:
                raise
            receiver_address = builder.alloca(
                value.type,
                name='class.magic.receiver.addr',
            )
            self._store_address(value, receiver_address, builder)
            return receiver_address

    def _emit_operator_method_call(
        self,
        type_name: str,
        method_name: str,
        receiver_address: ir.Value,
        argument_nodes: tuple[object, ...],
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        method = self._resolve_method_symbol(type_name, method_name)
        if method is None:
            raise FunctionEmissionError(
                f'El metodo magico {type_name}.{method_name} no existe'
            )
        if method.is_static:
            raise FunctionEmissionError(
                f'El metodo magico {type_name}.{method_name} no puede ser @static'
            )
        callee = self._functions.get(method.name)
        if callee is None:
            raise FunctionEmissionError(
                f'El metodo magico {method.name} no tiene emision LLVM'
            )

        parameters = list(method.signature.parameters)
        visible_parameters = [
            parameter for parameter in parameters
            if not (
                parameter.is_receiver
                or parameter.is_length
                or parameter.is_size
            )
        ]
        if len(visible_parameters) != len(argument_nodes):
            raise FunctionEmissionError(
                f'El metodo magico {method.name} recibio un numero invalido '
                'de argumentos'
            )

        arguments: list[ir.Value] = []
        argument_index = 0
        llvm_index = 0
        for parameter in parameters:
            target_type = callee.args[llvm_index].type
            if parameter.is_receiver:
                argument = self._coerce_value(
                    receiver_address,
                    target_type,
                    builder,
                )
            elif parameter.is_length or parameter.is_size:
                raise FunctionEmissionError(
                    f'El metodo magico {method.name} no admite Len_t/Size_t'
                )
            else:
                argument_node = argument_nodes[argument_index]
                if parameter.type_spec.array_depth:
                    argument = self._compile_array_argument(
                        argument_node,
                        target_type,
                        builder,
                        values,
                    )
                else:
                    argument = self._coerce_value(
                        self._compile_expression(
                            argument_node,
                            builder,
                            values,
                            expected_type=target_type,
                        ),
                        target_type,
                        builder,
                        signed=not self._expression_is_unsigned(argument_node),
                    )
                argument_index += 1
            arguments.append(argument)
            llvm_index += 1
        return builder.call(callee, arguments)

    def _compile_magic_operator(
        self,
        node: object,
        operator: str | None,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value | None:
        """Lower arithmetic operators implemented by class magic methods."""
        if (
            self._active_function_symbol is not None
            and getattr(self._active_function_symbol, 'is_method', False)
        ):
            return None
        if (
            getattr(node, 'operand', None) is not None
            and operator in MAGIC_UNARY_OPERATORS
        ):
            left_node = getattr(node, 'operand', None)
            names = MAGIC_UNARY_OPERATORS[operator]
            arguments = ()
        elif operator in MAGIC_BINARY_OPERATORS:
            left_node = getattr(node, 'left', None)
            right_node = getattr(node, 'right', None)
            names = MAGIC_BINARY_OPERATORS[operator]
            arguments = (right_node,)
        else:
            return None

        type_name = self._class_expression_type_name(left_node)
        if type_name is None:
            return None
        method_name = next(
            (
                name for name in names
                if self._resolve_method_symbol(type_name, name) is not None
            ),
            None,
        )
        if method_name is None:
            return None
        receiver_address = self._compile_class_receiver_address(
            left_node,
            type_name,
            builder,
            values,
        )
        return self._emit_operator_method_call(
            type_name,
            method_name,
            receiver_address,
            arguments,
            builder,
            values,
        )

    def _compile_class_condition(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value | None:
        """Lower an external class condition through its optional ``__eq__``."""
        type_name = self._class_expression_type_name(node)
        if type_name is None or self.type_registry is None:
            return None

        # Class methods are deliberately shielded from all automatic hooks.
        # Still emit the expression so a constructor or another call keeps its
        # normal evaluation semantics; the implicit comparison is false.
        if (
            self._active_function_symbol is not None
            and getattr(self._active_function_symbol, 'is_method', False)
        ):
            self._compile_expression(node, builder, values)
            return ir.Constant(ir.IntType(1), 0)

        receiver_address = self._compile_class_receiver_address(
            node,
            type_name,
            builder,
            values,
        )

        result = self._emit_magic_method_call(
            type_name,
            receiver_address,
            '__eq__',
            builder,
        )
        if result is None:
            return ir.Constant(ir.IntType(1), 0)
        if not isinstance(result.type, ir.IntType) or result.type.width != 1:
            raise FunctionEmissionError(
                f'El metodo {type_name}.__eq__ debe retornar bool'
            )
        return result


    @classmethod
    def _call_name(cls, primary: object, suffixes: list[object]) -> str | None:
        name = cls._identifier(primary)
        for suffix in suffixes:
            if getattr(suffix, 'name', None) != 'MEMBER_ACCESS':
                continue
            member = cls._identifier(suffix)
            if member is not None:
                name = f'{name}.{member}' if name else member
        return name

    def _method_call_target(
        self,
        primary: object,
        suffixes: list[object],
    ) -> tuple[object | None, object | None]:
        """Return the reserved method symbol and its explicit receiver node."""
        member_suffix = next(
            (
                suffix for suffix in reversed(suffixes)
                if getattr(suffix, 'name', None) == 'MEMBER_ACCESS'
            ),
            None,
        )
        if member_suffix is not None:
            base_name = self._identifier(primary)
            member_name = self._identifier(member_suffix)
            if not base_name or not member_name:
                return None, None
            base_spec = self._active_type_spec(base_name)
            owner_type = getattr(base_spec, 'name', None)
            if (
                owner_type is None
                and self.type_registry is not None
                and self.type_registry.aggregate(base_name) is not None
            ):
                owner_type = base_name
                class_reference = True
            else:
                class_reference = False
            method = self._resolve_method_symbol(owner_type, member_name)
            if method is None:
                return None, None
            if method.is_static and not class_reference:
                raise FunctionEmissionError(
                    f'El metodo estatico {owner_type}.{member_name} debe llamarse '
                    f'como {owner_type}.{member_name}'
                )
            if not method.is_static and class_reference:
                raise FunctionEmissionError(
                    f'El metodo {owner_type}.{member_name} requiere una instancia'
                )
            return method, None if method.is_static else primary

        source_name = self._identifier(primary)
        active = self._active_function_symbol
        if (
            source_name
            and active is not None
            and active.owner_type
            and not (
                self.type_registry is not None
                and self.type_registry.aggregate(source_name) is not None
            )
        ):
            method = self._resolve_method_symbol(active.owner_type, source_name)
            if method is not None:
                if method.is_static:
                    raise FunctionEmissionError(
                        f'El metodo estatico {active.owner_type}.{source_name} '
                        f'debe llamarse como {active.owner_type}.{source_name}'
                    )
                return method, None
        return None, None

    def _compile_array_argument(
        self,
        argument: object,
        target_type: ir.Type,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        if not isinstance(target_type, ir.PointerType):
            raise FunctionEmissionError(
                'El parametro array no tiene una representacion de puntero'
            )
        address = self._compile_address(argument, builder, values)
        pointee = address.type.pointee
        target_is_complete_array = isinstance(target_type.pointee, ir.ArrayType)
        if isinstance(pointee, ir.PointerType):
            pointer = builder.load(address)
        elif isinstance(pointee, ir.ArrayType) and not target_is_complete_array:
            pointer = builder.gep(
                address,
                [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), 0),
                ],
                inbounds=True,
            )
        elif isinstance(pointee, ir.ArrayType) and target_is_complete_array:
            pointer = address
        else:
            raise FunctionEmissionError(
                'El argumento no es un array compatible'
            )
        if pointer.type != target_type:
            raise FunctionEmissionError(
                'El elemento del array no coincide con el parametro de la funcion'
            )
        return pointer

    def _compile_chain_length(
        self,
        argument: object,
    ) -> int:
        current = self._unwrap(argument)
        kind = self._token_kind(current)
        if kind == 'STRING':
            value = self._token_value(current)
        elif kind == 'IDENT':
            name = str(self._token_value(current))
            info = self._active_values.get(name)
            if info is None:
                info = self._global_values.get(name)
            value = getattr(info, 'value', None)
            if (
                info is None
                or not getattr(info, 'is_literal', False)
                or getattr(getattr(info, 'type_spec', None), 'name', None)
                != 'chain'
            ):
                value = None
        else:
            value = None

        if not isinstance(value, str):
            raise FunctionEmissionError(
                'Len_t requiere un chain constante con longitud conocida '
                'en compilacion'
            )
        try:
            return len(value.encode('ascii')) + 1
        except UnicodeEncodeError as error:
            raise FunctionEmissionError(
                'Un chain usado por la ABI actual solo puede contener ASCII'
            ) from error

    def _compile_forwarded_expansion(
        self,
        argument: object,
        *,
        is_length: bool,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value | None:
        source_name = self._identifier(argument)
        if self._active_function_symbol is None or not source_name:
            return None
        forwarded = next(
            (
                parameter
                for parameter in self._active_function_symbol.signature.parameters
                if (
                    parameter.length_of == source_name
                    and parameter.is_length == is_length
                    and parameter.is_size == (not is_length)
                )
            ),
            None,
        )
        if forwarded is None:
            return None
        pointer = values.get(forwarded.name)
        if pointer is None:
            raise FunctionEmissionError(
                f'El metadato expandido {forwarded.name} no tiene '
                'almacenamiento LLVM'
            )
        return builder.load(pointer)

    def _compile_length_argument(
        self,
        argument: object,
        source_spec: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        if getattr(source_spec, 'name', None) == 'chain':
            forwarded = self._compile_forwarded_expansion(
                argument,
                is_length=True,
                builder=builder,
                values=values,
            )
            if forwarded is not None:
                return forwarded
            return ir.Constant(
                self._size_integer_type(),
                self._compile_chain_length(argument),
            )
        forwarded = self._compile_forwarded_expansion(
            argument,
            is_length=True,
            builder=builder,
            values=values,
        )
        if forwarded is not None:
            return forwarded
        address = self._compile_address(argument, builder, values)
        pointee = address.type.pointee
        if not isinstance(pointee, ir.ArrayType):
            raise FunctionEmissionError(
                'Len_t requiere un array con tamano conocido en compilacion'
            )
        return ir.Constant(self._size_integer_type(), pointee.count)

    @staticmethod
    def _llvm_type_size(value_type: ir.Type, pointer_size: int) -> int:
        if isinstance(value_type, ir.ArrayType):
            return value_type.count * ExpressionEmitterMixin._llvm_type_size(
                value_type.element,
                pointer_size,
            )
        if isinstance(value_type, ir.IntType):
            return max(1, (value_type.width + 7) // 8)
        if isinstance(value_type, ir.HalfType):
            return 2
        if isinstance(value_type, ir.FloatType):
            return 4
        if isinstance(value_type, ir.DoubleType):
            return 8
        if isinstance(value_type, ir.PointerType):
            return pointer_size
        raise FunctionEmissionError(
            f'No se puede determinar el tamano LLVM de {value_type}'
        )

    def _compile_array_element_size(
        self,
        argument: object,
        source_type: ir.Type,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        address = self._compile_address(argument, builder, values)
        pointee = address.type.pointee
        if not isinstance(pointee, ir.ArrayType):
            raise FunctionEmissionError(
                'Size_t requiere un array con tipo de elemento conocido'
            )
        return ir.Constant(
            self._size_integer_type(),
            self._llvm_type_size(pointee.element, self._pointer_size),
        )

    def _compile_size_argument(
        self,
        argument: object,
        source_type: ir.Type,
        source_spec: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        if (
            getattr(source_spec, 'array_depth', 0) > 0
            and not getattr(source_spec, 'pointer_level', 0)
        ):
            forwarded = self._compile_forwarded_expansion(
                argument,
                is_length=False,
                builder=builder,
                values=values,
            )
            if forwarded is not None:
                return forwarded
            return self._compile_array_element_size(
                argument,
                source_type,
                builder,
                values,
            )
        return ir.Constant(
            self._size_integer_type(),
            self._llvm_type_size(source_type, self._pointer_size),
        )

    @staticmethod
    def _visible_initializer_parameters(parameters: object) -> list[object]:
        return [
            parameter for parameter in parameters
            if not (
                getattr(parameter, 'is_length', False)
                or getattr(parameter, 'is_size', False)
                or getattr(parameter, 'is_receiver', False)
            )
        ]

    def _compile_initializer_argument(
        self,
        parameter: object,
        argument: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        target_type = self._function_parameter_type(parameter.type_spec)
        if parameter.type_spec.array_depth:
            return self._compile_array_argument(
                argument,
                target_type,
                builder,
                values,
            )
        return self._coerce_value(
            self._compile_expression(
                argument,
                builder,
                values,
                expected_type=target_type,
            ),
            target_type,
            builder,
            signed=not self._expression_is_unsigned(argument),
        )

    def _compile_aggregate_initializer(
        self,
        root_name: str,
        aggregate: object,
        initializer_values: dict[str, ir.Value],
        initializer_specs: dict[str, TypeSpec],
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
        result: ir.Value,
    ) -> ir.Value:
        """Inline one initializer and its statically known parent chain."""
        if self.type_registry is None:
            raise FunctionEmissionError(
                f'El iniciador de {root_name} requiere un registro de tipos LLVM'
            )

        previous_specs = self._active_specs
        previous_hook_suppression = self._suppress_magic_hooks
        self._active_specs = dict(initializer_specs)
        self._suppress_magic_hooks = True
        try:
            parent_name = getattr(aggregate, 'parent_type', None)
            parent = (
                self.type_registry.aggregate(parent_name)
                if parent_name
                else None
            )
            if parent is not None and getattr(parent, 'initializer_name', None):
                parent_initializer_name = getattr(
                    parent,
                    'initializer_name',
                    None,
                )
                call_name = getattr(aggregate, 'parent_initializer_name', None)
                arguments = getattr(
                    aggregate,
                    'parent_initializer_arguments',
                    (),
                )
                parameters = self._visible_initializer_parameters(
                    getattr(parent, 'constructor_parameters', ()) or ()
                )
                if call_name != parent_initializer_name:
                    raise FunctionEmissionError(
                        f'El iniciador de {root_name} no llama a '
                        f'super.{parent_initializer_name}(...)'
                    )
                if len(arguments) != len(parameters):
                    raise FunctionEmissionError(
                        f'super.{parent_initializer_name} de {root_name} recibio '
                        'un numero invalido de argumentos'
                    )

                parent_values = dict(initializer_values)
                parent_specs = dict(initializer_specs)
                parent_expression_values = dict(values)
                parent_expression_values.update(parent_values)
                for parameter, argument in zip(parameters, arguments):
                    compiled = self._compile_initializer_argument(
                        parameter,
                        argument,
                        builder,
                        parent_expression_values,
                    )
                    parent_values[parameter.name] = compiled
                    parent_specs[parameter.name] = parameter.type_spec
                    parent_expression_values[parameter.name] = compiled

                result = self._compile_aggregate_initializer(
                    root_name,
                    parent,
                    parent_values,
                    parent_specs,
                    builder,
                    values,
                    result,
                )

            self._active_specs = dict(initializer_specs)
            expression_values = dict(values)
            expression_values.update(initializer_values)
            for field in getattr(aggregate, 'fields', ()):
                initializer = getattr(field, 'initializer_node', None)
                if initializer is None:
                    continue
                field_type = self.type_registry.resolve(field.type_spec)
                value = self._coerce_value(
                    self._compile_expression(
                        initializer,
                        builder,
                        expression_values,
                        expected_type=field_type,
                    ),
                    field_type,
                    builder,
                    signed=not self._expression_is_unsigned(initializer),
                )
                path = self.type_registry.field_path(root_name, field.name)
                if path is None:
                    raise FunctionEmissionError(
                        f'El atributo {root_name}.{field.name} no tiene una ruta LLVM'
                    )
                result = builder.insert_value(result, value, path)
            return result
        finally:
            self._active_specs = previous_specs
            self._suppress_magic_hooks = previous_hook_suppression

    def _compile_constructor(
        self,
        name: str,
        call_suffix: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        if self.type_registry is None:
            raise FunctionEmissionError(
                f'El constructor {name} requiere un registro de tipos LLVM'
            )

        aggregate = self.type_registry.aggregate(name)
        parameters = getattr(aggregate, 'constructor_parameters', None)
        if aggregate is None or parameters is None:
            initializer_name = getattr(aggregate, 'initializer_name', None) or '__init__'
            raise FunctionEmissionError(
                f'La clase {name} no tiene un {initializer_name} utilizable'
            )

        arguments = next(
            (
                child for child in self._children(call_suffix)
                if getattr(child, 'name', None) == 'ARGUMENTS'
            ),
            None,
        )
        argument_items: list[object] = []
        if arguments is not None:
            container = next(iter(self._children(arguments)), None)
            argument_items = self._children(container)

        visible_parameters = self._visible_initializer_parameters(parameters)
        if len(argument_items) != len(visible_parameters):
            raise FunctionEmissionError(
                f'El constructor {name} recibio un numero invalido de argumentos'
            )

        constructor_values = dict(values)
        constructor_specs = dict(self._active_specs)
        for parameter, argument in zip(visible_parameters, argument_items):
            compiled = self._compile_initializer_argument(
                parameter,
                argument,
                builder,
                values,
            )
            constructor_values[parameter.name] = compiled
            constructor_specs[parameter.name] = parameter.type_spec

        result = self.type_registry.default_constant(TypeSpec(name))
        return self._compile_aggregate_initializer(
            name,
            aggregate,
            constructor_values,
            constructor_specs,
            builder,
            values,
            result,
        )

    def _compile_frontend_constructor(
        self,
        name: str,
        source: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        """Lower ``Class = source`` through the class frontend hook."""
        if self.type_registry is None:
            raise FunctionEmissionError(
                f'El iniciador frontend de {name} requiere un registro de tipos LLVM'
            )

        aggregate = self.type_registry.aggregate(name)
        parameters = getattr(aggregate, 'constructor_parameters', None)
        if (
            aggregate is None
            or getattr(aggregate, 'initializer_name', None) != '__frontend__'
            or parameters is None
        ):
            raise FunctionEmissionError(
                f'La clase {name} no tiene un __frontend__ utilizable'
            )

        visible_parameters = self._visible_initializer_parameters(parameters)
        if len(visible_parameters) != 1:
            raise FunctionEmissionError(
                f'El __frontend__ de {name} debe recibir exactamente un parametro'
            )

        parameter = visible_parameters[0]
        compiled = self._compile_initializer_argument(
            parameter,
            source,
            builder,
            values,
        )

        constructor_values = dict(values)
        constructor_values[parameter.name] = compiled
        constructor_specs = dict(self._active_specs)
        constructor_specs[parameter.name] = parameter.type_spec
        result = self.type_registry.default_constant(TypeSpec(name))
        return self._compile_aggregate_initializer(
            name,
            aggregate,
            constructor_values,
            constructor_specs,
            builder,
            values,
            result,
        )

    def _compile_call(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        """Emit a CALL or POSTFIX_EXPR whose suffixes contain a call."""
        children = self._children(node)
        primary = children[0] if children else None
        suffixes: list[object] = []
        for child in children[1:]:
            suffixes.extend(
                self._children(child) if isinstance(child, list) else [child]
            )
        call_suffix = next(
            (
                suffix for suffix in suffixes
                if getattr(suffix, 'name', None) == 'CALL_SUFFIX'
            ),
            None,
        )
        if call_suffix is None:
            raise FunctionEmissionError('La llamada no tiene argumentos')

        method, receiver_node = self._method_call_target(primary, suffixes)
        receiver_value = None
        if method is not None:
            name = method.name
            callee = self._functions.get(name)
            if callee is None:
                raise FunctionEmissionError(
                    f'El metodo {name} no tiene emision LLVM'
                )
            if not method.is_static:
                if receiver_node is None:
                    receiver_value = self._method_receiver_address(builder, values)
                else:
                    receiver_value = self._compile_address(
                        receiver_node,
                        builder,
                        values,
                    )
        else:
            name = self._call_name(primary, suffixes)
        if (
            method is None
            and name is not None
            and self.type_registry is not None
            and self.type_registry.aggregate(name) is not None
            and getattr(
                self.type_registry.aggregate(name),
                'constructor_parameters',
                None,
            ) is not None
        ):
            return self._compile_constructor(name, call_suffix, builder, values)
        if method is None:
            callee = self._functions.get(name or '')
        if callee is None:
            raise FunctionEmissionError(
                f'La funcion {name or "<anonima>"} no tiene emision LLVM'
            )
        arguments = next(
            (
                child for child in self._children(call_suffix)
                if getattr(child, 'name', None) == 'ARGUMENTS'
            ),
            None,
        )
        argument_items: list[object] = []
        if arguments is not None:
            container = next(iter(self._children(arguments)), None)
            argument_items = self._children(container)
        symbol = self._symbols.get(name or '')
        parameters = list(getattr(symbol.signature, 'parameters', ())) if symbol else []
        visible_parameters = [
            parameter for parameter in parameters
            if not (
                getattr(parameter, 'is_length', False)
                or getattr(parameter, 'is_size', False)
                or getattr(parameter, 'is_receiver', False)
            )
        ]
        if len(argument_items) != len(visible_parameters):
            raise FunctionEmissionError(
                f'La funcion {name or "<anonima>"} recibio un numero invalido '
                'de argumentos'
            )
        compiled: list[ir.Value] = []
        source_arguments = dict(zip(
            (parameter.name for parameter in visible_parameters),
            argument_items,
        ))
        source_parameters = {
            parameter.name: parameter
            for parameter in visible_parameters
        }
        source_llvm_indices: dict[str, int] = {}
        for index, parameter in enumerate(parameters):
            if not (
                getattr(parameter, 'is_length', False)
                or getattr(parameter, 'is_size', False)
                or getattr(parameter, 'is_receiver', False)
            ):
                source_llvm_indices[parameter.name] = index
        argument_index = 0
        llvm_index = 0
        for parameter in parameters:
            if getattr(parameter, 'is_receiver', False):
                if receiver_value is None:
                    raise FunctionEmissionError(
                        f'El metodo {name or "<anonimo>"} requiere una instancia'
                    )
                target_type = callee.args[llvm_index].type
                compiled.append(
                    self._coerce_value(receiver_value, target_type, builder)
                )
                llvm_index += 1
                continue

            if parameter.is_length or parameter.is_size:
                source = source_arguments.get(parameter.length_of or '')
                source_parameter = source_parameters.get(parameter.length_of or '')
                if source is None:
                    raise FunctionEmissionError(
                        'Len_t/Size_t no tiene un valor fuente asociado'
                    )
                if source_parameter is None:
                    raise FunctionEmissionError(
                        'Len_t/Size_t no tiene un parametro fuente asociado'
                    )
                source_llvm_type = callee.args[
                    source_llvm_indices[source_parameter.name]
                ].type
                if parameter.is_length:
                    compiled.append(
                        self._compile_length_argument(
                            source,
                            source_parameter.type_spec,
                            builder,
                            values,
                        )
                    )
                else:
                    compiled.append(
                        self._compile_size_argument(
                            source,
                            source_llvm_type,
                            source_parameter.type_spec,
                            builder,
                            values,
                        )
                    )
                llvm_index += 1
                continue

            if argument_index >= len(argument_items):
                raise FunctionEmissionError(
                    f'La funcion {name or "<anonima>"} recibio un numero invalido '
                    'de argumentos'
                )
            argument = argument_items[argument_index]
            target_type = callee.args[llvm_index].type
            if parameter.type_spec.array_depth:
                compiled.append(
                    self._compile_array_argument(
                        argument,
                        target_type,
                        builder,
                        values,
                    )
                )
            else:
                compiled.append(
                    self._coerce_value(
                        self._compile_expression(
                            argument,
                            builder,
                            values,
                            expected_type=target_type,
                        ),
                        target_type,
                        builder,
                        signed=not self._expression_is_unsigned(argument),
                    )
                )
            argument_index += 1
            llvm_index += 1
        result = builder.call(callee, compiled)
        return_type = getattr(
            getattr(symbol, 'signature', None),
            'return_type',
            None,
        )
        if (
            return_type is not None
            and return_type.name == 'Never'
            and return_type.pointer_level == 0
            and return_type.array_depth == 0
        ):
            builder.unreachable()
        return result


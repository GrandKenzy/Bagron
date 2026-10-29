from __future__ import annotations

from dataclasses import dataclass

from llvmlite import ir

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

    def _memory_place(
        self,
        address: ir.Value,
        *,
        alignment: int | None = None,
        volatile: bool = False,
    ) -> _MemoryPlace:
        if not isinstance(address.type, ir.PointerType):
            raise FunctionEmissionError('La expresion no tiene direccion LLVM')
        value_type = address.type.pointee
        return _MemoryPlace(
            address=address,
            value_type=value_type,
            alignment=self._place_alignment(value_type, alignment),
            volatile=volatile or self._aggregate_volatile(value_type),
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
            return self._compile_place(children[0], builder, values)

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
            return self._compile_place(inner, builder, values)

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
                        )
                    else:
                        # The semantic pass guarantees that this is a pointer
                        # access.  A scalar GEP keeps raw-pointer indexing
                        # available for future pointer arithmetic without
                        # inventing a second address representation.
                        place = self._memory_place(
                            builder.gep(address, [index], inbounds=False),
                            alignment=1,
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
                    alignment = 1 if layout.symbol.is_packed else min(
                        place.alignment or layout.alignment,
                        self._place_alignment(field_type) or 1,
                    )
                    place = self._memory_place(
                        address,
                        alignment=alignment,
                        volatile=volatile,
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
    ) -> ir.Value:
        place = self._compile_place(node, builder, values)
        if isinstance(place, _BitfieldPlace):
            raise FunctionEmissionError(
                'Un campo de flags no tiene una direccion independiente'
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

        if type(current).__name__ == 'ASTUnaryOp':
            operator = getattr(
                getattr(current.operator, 'token', None),
                'name',
                None,
            )
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
            left = self._compile_expression(current.left, builder, values)
            right = self._compile_expression(current.right, builder, values)
            operator = getattr(
                getattr(current.operator, 'token', None),
                'name',
                None,
            )
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
                    address = self._compile_address(primary, builder, values)
                    pointee = address.type.pointee
                    if isinstance(pointee, ir.ArrayType):
                        return ir.Constant(self._size_integer_type(), pointee.count)
                    if self._is_array_descriptor_type(pointee):
                        descriptor = builder.load(address)
                        return builder.extract_value(descriptor, 1)
                    raise FunctionEmissionError(
                        'La longitud solo puede obtenerse de un array'
                    )
                place = self._compile_place(current, builder, values)
                return self._load_place(place, builder)

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
            elif name in self.module.globals:
                result = self.module.globals[name]
            else:
                raise FunctionEmissionError(
                    f'La variable {name} no tiene emision LLVM en esta fase'
                )
            active_spec = self._active_specs.get(name)
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

        name = self._call_name(primary, suffixes)
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
            ):
                source_llvm_indices[parameter.name] = index
        argument_index = 0
        llvm_index = 0
        for parameter in parameters:
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
        return builder.call(callee, compiled)


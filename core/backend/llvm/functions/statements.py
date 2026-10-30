from __future__ import annotations

from llvmlite import ir

from core.backend.llvm.types import (
    LLVMTypeError,
    constant_value,
    default_value,
    scalar_type,
    value_type,
)
from core.frontend.objects import FunctionSymbol, TypeSpec
from core.frontend.tools.types import (
    FOR_ITERATOR_TYPES,
    INTEGER_TYPES,
    SIGNED_INTEGER_TYPES,
    UNSIGNED_INTEGER_TYPES,
    buffer_capacity,
    is_buffer_type,
    target_iteration_limit,
)

from .errors import FunctionEmissionError


class StatementEmitterMixin:
    """LLVM emission for declarations, control flow, and function bodies."""

    def _iterator_address_is_taken(self, node: object, name: str) -> bool:
        """Return whether ``$name`` needs a real address inside this body.

        Optimised loops use a phi value only while the iterator remains a
        value.  Taking its address keeps the historical addressable alloca,
        which is required for calls and pointer dereferences in the body.
        """
        current = self._unwrap(node)
        if type(current).__name__ == 'ASTUnaryOp':
            operator = getattr(
                getattr(current, 'operator', None),
                'token',
                None,
            )
            if getattr(operator, 'name', None) == 'DOLLAR':
                operand = getattr(current, 'operand', None)
                if self._identifier(operand) == name:
                    return True
            return self._iterator_address_is_taken(
                getattr(current, 'operand', None),
                name,
            )
        return any(
            self._iterator_address_is_taken(child, name)
            for child in self._children(current)
        )

    def _unwrap_buffer_value(self, node: object) -> object:
        current = self._unwrap(node)
        while getattr(current, 'name', None) == 'PAREN_VALUE':
            inner = next(
                (
                    child for child in self._children(current)
                    if getattr(child, 'name', None) == 'VALUE'
                ),
                None,
            )
            if inner is None:
                break
            current = self._unwrap(inner)
        return current

    @classmethod
    def _assignment_operator(cls, node: object) -> str | None:
        operators = {
            'ASSIGN': '=',
            'PLUS_ASSIGN': '+=',
            'MINUS_ASSIGN': '-=',
            'STAR_ASSIGN': '*=',
            'SLASH_ASSIGN': '/=',
            'PERCENT_ASSIGN': '%=',
            'AND_ASSIGN': '&=',
            'OR_ASSIGN': '|=',
            'XOR_ASSIGN': '^=',
            'SHL_ASSIGN': '<<=',
            'SHR_ASSIGN': '>>=',
        }
        for child in cls._children(node):
            operator = operators.get(cls._token_kind(child))
            if operator is not None:
                return operator
        return None

    @classmethod
    def _assignment_value(cls, node: object) -> object | None:
        return next(
            (
                child for child in cls._children(node)
                if getattr(child, 'name', None) == 'VALUE'
            ),
            None,
        )

    def _emit_buffer_allocation(
        self,
        capacity: int,
        builder: ir.IRBuilder,
    ) -> ir.Value:
        if self.type_registry is None:
            raise FunctionEmissionError(
                'El buffer requiere un registro de tipos LLVM'
            )
        size_type = self._size_integer_type()
        byte_pointer = ir.IntType(8).as_pointer()
        malloc = self._runtime_function('malloc', byte_pointer, [size_type])
        data = builder.call(
            malloc,
            [ir.Constant(size_type, capacity)],
            name='buffer.data',
        )
        is_null = builder.icmp_unsigned(
            '==',
            data,
            ir.Constant(byte_pointer, None),
        )
        function = builder.function
        if function is None:
            raise FunctionEmissionError(
                'La reserva de buffer requiere una funcion'
            )
        block_id = len(function.blocks)
        ok_block = function.append_basic_block(name=f'buffer.alloc.ok.{block_id}')
        fail_block = function.append_basic_block(
            name=f'buffer.alloc.fail.{block_id}'
        )
        builder.cbranch(is_null, fail_block, ok_block)
        fail_builder = ir.IRBuilder(fail_block)
        self._emit_trap(fail_builder)
        builder.position_at_end(ok_block)

        memset = self._runtime_function(
            'memset',
            byte_pointer,
            [byte_pointer, ir.IntType(32), size_type],
        )
        builder.call(
            memset,
            [data, ir.Constant(ir.IntType(32), 0), ir.Constant(size_type, capacity)],
        )
        descriptor_type = self.type_registry.buffer_type()
        descriptor = ir.Constant(descriptor_type, None)
        descriptor = builder.insert_value(descriptor, data, 0)
        return builder.insert_value(
            descriptor,
            ir.Constant(size_type, capacity),
            1,
        )

    @staticmethod
    def _aggregate_byte_size(value_type: ir.Type) -> int | None:
        """Return the byte size for the array shapes handled by this emitter."""
        if isinstance(value_type, ir.ArrayType):
            element_size = StatementEmitterMixin._aggregate_byte_size(
                value_type.element,
            )
            return None if element_size is None else value_type.count * element_size
        if isinstance(value_type, ir.IntType):
            return max(1, (value_type.width + 7) // 8)
        if isinstance(value_type, ir.HalfType):
            return 2
        if isinstance(value_type, ir.FloatType):
            return 4
        if isinstance(value_type, ir.DoubleType):
            return 8
        return None

    def _emit_large_zero_initialization(
        self,
        pointer: ir.Value,
        value_type: ir.Type,
        builder: ir.IRBuilder,
    ) -> bool:
        """Zero large arrays without materialising an aggregate store.

        Keeping the initialization as ``memset`` lets SROA promote nearby
        scalar locals without expanding a large byte array into one IR store
        per element.
        """
        if self._aggregate_volatile(value_type):
            return False
        byte_size = self._aggregate_byte_size(value_type)
        if byte_size is None or byte_size <= 1024:
            return False
        byte_pointer = builder.bitcast(pointer, ir.IntType(8).as_pointer())
        size_type = self._size_integer_type()
        memset = self._runtime_function(
            'memset',
            ir.IntType(8).as_pointer(),
            [ir.IntType(8).as_pointer(), ir.IntType(32), size_type],
        )
        builder.call(
            memset,
            [
                byte_pointer,
                ir.Constant(ir.IntType(32), 0),
                ir.Constant(size_type, byte_size),
            ],
        )
        return True

    def _buffer_literal_items(self, value_node: object) -> list[object]:
        current = self._unwrap_buffer_value(value_node)
        if getattr(current, 'name', None) != 'ARRAY_VALUE':
            return []
        container = next(
            (
                child for child in self._children(current)
                if isinstance(child, (list, tuple))
                or hasattr(child, 'items')
                or hasattr(child, 'nodes')
            ),
            None,
        )
        return self._children(container) if container is not None else []

    def _emit_buffer_initializer(
        self,
        name: str,
        value_node: object,
        pointer: ir.Value,
        semantic_value: object | None,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> None:
        spec = self._active_specs.get(name)
        capacity = buffer_capacity(spec) if spec is not None else None
        if capacity is None:
            raise FunctionEmissionError(
                f'El buffer {name} no tiene una capacidad conocida'
            )

        current = self._unwrap_buffer_value(value_node)
        if type(current).__name__ == 'ASTBinaryOp':
            operator = getattr(
                getattr(current.operator, 'token', None),
                'name',
                None,
            )
            if operator != 'PLUS':
                raise FunctionEmissionError(
                    'La inicializacion de buffer solo admite concatenacion con +'
                )
            result = self._compile_expression(
                value_node,
                builder,
                values,
                expected_type=pointer.type.pointee,
            )
            self._store_address(
                self._coerce_value(result, pointer.type.pointee, builder),
                pointer,
                builder,
                alignment=getattr(pointer, 'align', None),
            )
            return

        result = self._emit_buffer_allocation(capacity, builder)
        if (
            semantic_value is not None
            and getattr(semantic_value, 'is_literal', False)
            and getattr(getattr(semantic_value, 'type_spec', None), 'array_depth', 0)
        ):
            data, _ = self._buffer_data_and_length(result, builder)
            size_type = self._size_integer_type()
            for index, item in enumerate(self._buffer_literal_items(value_node)):
                item_value = self._coerce_value(
                    self._compile_expression(
                        item,
                        builder,
                        values,
                        expected_type=ir.IntType(8),
                    ),
                    ir.IntType(8),
                    builder,
                    signed=False,
                )
                address = builder.gep(
                    data,
                    [ir.Constant(size_type, index)],
                    inbounds=False,
                )
                self._store_address(item_value, address, builder, alignment=1)

        self._store_address(
            result,
            pointer,
            builder,
            alignment=getattr(pointer, 'align', None),
        )

    def _emit_local_declaration(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> None:
        declaration = next(
            (
                child for child in self._children(node)
                if getattr(child, 'name', None)
                in {'VAR_DECLARATION', 'VAR_INITIALIZATION'}
            ),
            None,
        )
        if declaration is None:
            raise FunctionEmissionError('La declaracion local es invalida')

        name = self._identifier(declaration)
        if name is None or name not in values:
            raise FunctionEmissionError(
                f'La variable local {name or "<anonima>"} no tiene almacenamiento LLVM'
            )

        if name in self._active_direct_chains:
            # Optimized chain locals already point into module rodata.
            return

        value_node = next(
            (
                child for child in self._children(declaration)
                if getattr(child, 'name', None) == 'VALUE'
            ),
            None,
        )
        if value_node is None:
            return

        pointer = values[name]
        semantic_value = self._active_values.get(name)
        result = None
        variable = None
        if self._active_function_symbol is not None:
            variable = self._active_function_symbol.local_variables.get(name)
        if is_buffer_type(self._active_specs.get(name, TypeSpec('void'))):
            self._emit_buffer_initializer(
                name,
                value_node,
                pointer,
                semantic_value,
                builder,
                values,
            )
            return
        if (
            getattr(variable, 'uses_frontend_initializer', False)
            and self.type_registry is not None
        ):
            target_name = self._identified_name(pointer.type.pointee)
            if target_name is not None:
                result = self._compile_frontend_constructor(
                    target_name,
                    value_node,
                    builder,
                    values,
                )
        if (
            semantic_value is not None
            and isinstance(pointer.type.pointee, ir.ArrayType)
            and getattr(semantic_value, 'is_literal', False)
        ):
            try:
                result = constant_value(
                    self._active_specs[name],
                    semantic_value,
                    self.type_registry,
                )
            except LLVMTypeError:
                # Keep the normal expression path as the diagnostic source
                # for non-static aggregate initializers.
                result = None
        if result is None:
            result = self._compile_expression(
                value_node,
                builder,
                values,
                expected_type=pointer.type.pointee,
            )
        result = self._coerce_value(result, pointer.type.pointee, builder)
        self._store_address(
            result,
            pointer,
            builder,
            alignment=getattr(pointer, 'align', None),
            volatile=self._aggregate_volatile(pointer.type.pointee),
        )

    def _emit_assignment(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
        symbol: FunctionSymbol,
    ) -> None:
        target = next(
            (
                child for child in self._children(node)
                if getattr(child, 'name', None) == 'ASSIGN_TARGET'
            ),
            None,
        )
        name = self._identifier(target) if target is not None else None
        if target is None:
            raise FunctionEmissionError(
                f'La asignacion de {name or "<anonima>"} no tiene almacenamiento LLVM'
            )

        place = self._compile_place(
            target,
            builder,
            values,
            hook_mode='write',
        )

        value_node = self._assignment_value(node)
        operator = self._assignment_operator(node)
        if value_node is None or operator is None:
            raise FunctionEmissionError('La asignacion local es invalida')

        target_type = (
            place.field_type
            if hasattr(place, 'field_type')
            else place.value_type
        )
        right = self._coerce_value(
            self._compile_expression(
                value_node,
                builder,
                values,
                expected_type=target_type,
            ),
            target_type,
            builder,
            signed=not self._expression_is_unsigned(value_node),
        )
        if operator == '=':
            result = right
        else:
            left = self._load_place(place, builder)
            unsigned = bool(getattr(place, 'unsigned', False))
            if symbol.scope is not None and name is not None:
                type_spec = self._active_type_spec(name)
                unsigned = unsigned or (
                    getattr(type_spec, 'name', None) in UNSIGNED_INTEGER_TYPES
                )
            operations = {
                '+=': builder.add,
                '-=': builder.sub,
                '*=': builder.mul,
                '/=': builder.udiv if unsigned else builder.sdiv,
                '%=': builder.urem if unsigned else builder.srem,
                '&=': builder.and_,
                '|=': builder.or_,
                '^=': builder.xor,
                '<<=': builder.shl,
                '>>=': builder.lshr if unsigned else builder.ashr,
            }
            operation = operations.get(operator)
            if operation is None:
                raise FunctionEmissionError(
                    f'Operador de asignacion no soportado: {operator}'
                )
            result = operation(left, right)
        self._store_place(result, place, builder)
        if hasattr(place, 'after_hooks') and place.after_hooks:
            self._emit_after_access_hooks(
                place.after_hooks,
                builder,
                hook_mode='write',
            )

    def _emit_buffer_deletion(
        self,
        value_node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> bool:
        """Free a buffer through its addressable descriptor place.

        Resolving the place, instead of deriving an address from an identifier,
        also covers a buffer stored in an aggregate field.  A future ownership
        ABI can reuse this exact place resolution for parameters and returns.
        """
        try:
            place = self._compile_place(value_node, builder, values)
        except FunctionEmissionError:
            return False
        value_type = getattr(place, 'value_type', None)
        if not self._is_buffer_descriptor_type(value_type):
            return False

        descriptor = self._load_place(place, builder)
        data, _ = self._buffer_data_and_length(descriptor, builder)
        free = self._runtime_function(
            'free',
            ir.VoidType(),
            [ir.IntType(8).as_pointer()],
        )
        builder.call(free, [data])
        self._store_address(
            ir.Constant(descriptor.type, None),
            place.address,
            builder,
            alignment=getattr(place, 'alignment', None),
            volatile=getattr(place, 'volatile', False),
        )
        return True

    def _emit_deletion(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> None:
        value_node = next(
            (
                child for child in self._children(node)
                if getattr(child, 'name', None) == 'VALUE'
            ),
            None,
        )
        if value_node is None:
            raise FunctionEmissionError('Del no contiene una instancia')

        if self._emit_buffer_deletion(value_node, builder, values):
            return

        type_name = self._class_expression_type_name(value_node)
        if type_name is None:
            raise FunctionEmissionError(
                'Del requiere una instancia escalar de class'
            )
        method = self._resolve_method_symbol(type_name, '__deletion__')
        if method is None:
            # Del is intentionally a no-op when the class has no deletion hook,
            # but the expression is still evaluated for ordinary side effects.
            self._compile_expression(value_node, builder, values)
            return

        receiver_address = self._compile_class_receiver_address(
            value_node,
            type_name,
            builder,
            values,
        )
        self._emit_operator_method_call(
            type_name,
            '__deletion__',
            receiver_address,
            (),
            builder,
            values,
        )

    def _prepare_values(
        self,
        symbol: FunctionSymbol,
        builder: ir.IRBuilder,
        arguments: list[ir.Argument],
    ) -> dict[str, ir.Value]:
        values: dict[str, ir.Value] = {}
        self._active_direct_chains = set()
        scope = symbol.scope
        if scope is None:
            return values

        chain_parameters = {
            parameter.name
            for parameter in symbol.signature.parameters
            if parameter.type_spec.name == 'chain'
        }
        array_parameters = {
            parameter.name
            for parameter in symbol.signature.parameters
            if (
                parameter.type_spec.array_depth
                and not parameter.is_length
                and not parameter.is_size
                and not parameter.is_region
            )
        }
        region_parameters = {
            parameter.name
            for parameter in symbol.signature.parameters
            if parameter.is_region
        }
        variables = getattr(symbol, 'local_variables', None)
        if variables is None:
            variables = scope.namespace
        direct_parameters = {
            parameter.name
            for parameter in symbol.signature.parameters
            if (
                self._optimization_profile in {'prod', 'high'}
                and (
                    parameter.is_length
                    or parameter.is_size
                    or parameter.type_spec.name == 'chain'
                )
            )
        }
        for name, variable in variables.items():
            if name in direct_parameters:
                # Len_t/Size_t metadata and optimized chain parameters are
                # already SSA values; neither needs a local storage slot.
                continue
            if (
                self._optimization_profile in {'prod', 'high'}
                and variable.type_spec.name == 'chain'
                and getattr(variable, 'value_info', None) is not None
                and getattr(variable.value_info, 'is_literal', False)
                and isinstance(getattr(variable.value_info, 'value', None), str)
            ):
                self._active_direct_chains.add(name)
                values[name] = self._string_pointer(
                    variable.value_info.value,
                    builder,
                )
                continue
            try:
                if name in array_parameters:
                    # Arrays are passed by reference.  Keep only the pointer
                    # slot here so indexing and assignments reach the caller's
                    # complete array storage without making a copy.
                    local_type = self._function_parameter_type(variable.type_spec)
                elif name in chain_parameters:
                    # A chain parameter is passed as a pointer to its static
                    # NUL-terminated storage.  Locals/globals remain arrays.
                    local_type = ir.IntType(8).as_pointer()
                else:
                    local_type = value_type(
                        variable.type_spec,
                        getattr(variable, 'value_info', None),
                        self.type_registry,
                    )
            except (AttributeError, TypeError, ValueError, LLVMTypeError) as error:
                raise FunctionEmissionError(
                    f'La variable local {name} no tiene un tipo LLVM soportado'
                ) from error
            pointer = builder.alloca(local_type, name=f'{name}.addr')
            if self.type_registry is not None:
                pointer.align = self.type_registry.abi_alignment(local_type)
            values[name] = pointer
            initial_value = (
                ir.Constant(local_type, 0)
                if name in region_parameters
                else ir.Constant(local_type, None)
                if name in chain_parameters or name in array_parameters
                else default_value(
                    variable.type_spec,
                    getattr(variable, 'value_info', None),
                    self.type_registry,
                )
            )
            if not self._emit_large_zero_initialization(
                pointer,
                local_type,
                builder,
            ):
                self._store_address(
                    initial_value,
                    pointer,
                    builder,
                    alignment=pointer.align,
                    volatile=self._aggregate_volatile(local_type),
                )

        runtime_parameters = [
            parameter
            for parameter in symbol.signature.parameters
            if not parameter.is_region
        ]
        for parameter, argument in zip(runtime_parameters, arguments):
            if (
                self._optimization_profile in {'prod', 'high'}
                and parameter.type_spec.name == 'chain'
            ):
                # The chain ABI is already an i8* to immutable bytes. Keep
                # the incoming pointer in SSA instead of boxing it in i8**.
                argument.name = parameter.name
                values[parameter.name] = argument
                self._active_direct_chains.add(parameter.name)
                continue
            if (
                self._optimization_profile in {'prod', 'high'}
                and (parameter.is_length or parameter.is_size)
            ):
                values[parameter.name] = argument
                continue
            pointer = values.get(parameter.name)
            if pointer is None:
                raise FunctionEmissionError(
                    f'El parametro {parameter.name} no tiene almacenamiento LLVM'
                )
            argument.name = parameter.name
            self._store_address(
                self._coerce_value(argument, pointer.type.pointee, builder),
                pointer,
                builder,
                alignment=getattr(pointer, 'align', None),
                volatile=self._aggregate_volatile(pointer.type.pointee),
            )
        return values


    @classmethod
    def _for_signature(cls, node: object) -> object | None:
        return next(
            (
                child for child in cls._children(node)
                if getattr(child, 'name', None) == 'FOR_SIGNATURE'
            ),
            None,
        )

    @classmethod
    def _statement_body(cls, node: object) -> object | None:
        return next(
            (
                child for child in cls._children(node)
                if getattr(child, 'name', None) == 'STATEMENT_BODY'
            ),
            None,
        )

    def _emit_return(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> None:
        return_node = next(
            (
                child for child in self._children(node)
                if getattr(child, 'name', None) == 'VALUE'
            ),
            None,
        )
        return_type = builder.function.function_type.return_type
        active_symbol = self._active_function_symbol
        if (
            active_symbol is not None
            and active_symbol.signature.return_type.name == 'Never'
            and active_symbol.signature.return_type.pointer_level == 0
            and active_symbol.signature.return_type.array_depth == 0
        ):
            raise FunctionEmissionError(
                f'La funcion Never {active_symbol.name} no puede usar return'
            )
        if isinstance(return_type, ir.VoidType):
            if return_node is not None:
                raise FunctionEmissionError(
                    'Una funcion void no puede retornar un valor'
                )
            builder.ret_void()
            return
        if return_node is None:
            raise FunctionEmissionError('El return necesita un valor')
        result = self._compile_expression(
            return_node,
            builder,
            values,
            expected_type=return_type,
        )
        result = self._coerce_value(
            result,
            return_type,
            builder,
            signed=not self._expression_is_unsigned(return_node),
        )
        builder.ret(result)

    def _emit_for(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
        function: ir.Function,
        symbol: FunctionSymbol,
    ) -> None:
        signature = self._for_signature(node)
        body = self._statement_body(node)
        if signature is None or body is None:
            raise FunctionEmissionError('El for no tiene firma o cuerpo')

        name = self._identifier(signature)
        if name is None or symbol.scope is None:
            raise FunctionEmissionError('El for no tiene un iterador valido')
        type_spec = getattr(symbol, 'loop_iterators', {}).get(name)
        if type_spec is None:
            iterator_symbol = symbol.scope.resolve(name)
            type_spec = getattr(iterator_symbol, 'type_spec', None)
        if type_spec is None:
            raise FunctionEmissionError(f'No existe el iterador {name}')
        array_form = any(
            self._token_value(child) == 'in'
            for child in self._children(signature)
        )
        allowed_types = INTEGER_TYPES if array_form else FOR_ITERATOR_TYPES
        if (
            type_spec.name not in allowed_types
            or type_spec.pointer_level
            or type_spec.array_depth
        ):
            raise FunctionEmissionError(
                f'El iterador {name} no tiene un tipo entero escalar valido'
            )
        iterator_type = scalar_type(type_spec)
        if not isinstance(iterator_type, ir.IntType):
            raise FunctionEmissionError(f'El iterador {name} no es entero')

        range_values = [
            child for child in self._children(signature)
            if getattr(child, 'name', None) == 'VALUE'
        ]
        if array_form and len(range_values) != 1:
            raise FunctionEmissionError(
                f'El for de {name} debe tener exactamente un array fuente'
            )
        if not array_form and len(range_values) != 3:
            raise FunctionEmissionError(
                f'El rango de {name} debe tener start, end y step'
            )

        end_source = None
        if array_form:
            array_node = range_values[0]
            source_spec = self._active_type_spec(
                self._identifier(array_node) or ''
            )
            end_source = self._compile_forwarded_expansion(
                array_node,
                is_length=True,
                builder=builder,
                values=values,
            )
            if end_source is None:
                end_source = self._compile_length_argument(
                    array_node,
                    source_spec,
                    builder,
                    values,
                )
            start = ir.Constant(iterator_type, 0)
            end = self._coerce_int(
                end_source,
                iterator_type,
                builder,
                signed=False,
            )
            step = ir.Constant(iterator_type, 1)
        else:
            start = self._coerce_int(
                self._compile_expression(range_values[0], builder, values),
                iterator_type,
                builder,
                signed=False,
            )
            end = self._coerce_int(
                self._compile_expression(range_values[1], builder, values),
                iterator_type,
                builder,
                signed=False,
            )
            step = self._coerce_int(
                self._compile_expression(range_values[2], builder, values),
                iterator_type,
                builder,
                signed=False,
            )

        block_id = len(function.blocks)
        iterator_is_signed = type_spec.name in SIGNED_INTEGER_TYPES
        iterator_max = (
            (1 << (iterator_type.width - 1)) - 1
            if iterator_is_signed
            else (1 << iterator_type.width) - 1
        )
        target_limit = min(
            target_iteration_limit(self._pointer_size),
            iterator_max,
        )
        range_limit = ir.Constant(iterator_type, target_limit)
        step_valid_block = function.append_basic_block(
            name=f'for.step.valid.{block_id}'
        )
        range_invalid_block = function.append_basic_block(
            name=f'for.range.invalid.{block_id}'
        )
        condition_block = function.append_basic_block(
            name=f'for.cond.{block_id}'
        )
        body_block = function.append_basic_block(name=f'for.body.{block_id}')
        step_block = function.append_basic_block(name=f'for.step.{block_id}')
        update_block = function.append_basic_block(
            name=f'for.update.{block_id}'
        )
        after_block = function.append_basic_block(name=f'for.end.{block_id}')

        values_in_range = builder.and_(
            builder.icmp_unsigned('<=', start, range_limit),
            builder.icmp_unsigned('<=', end, range_limit),
        )
        values_in_range = builder.and_(
            values_in_range,
            builder.icmp_unsigned('<=', step, range_limit),
        )
        zero = ir.Constant(iterator_type, 0)
        nonzero = builder.icmp_unsigned('!=', step, zero)
        valid_range = builder.and_(values_in_range, nonzero)
        if array_form:
            if not isinstance(end_source.type, ir.IntType):
                raise FunctionEmissionError(
                    f'El tamano del array de {name} no es entero'
                )
            source_max = (1 << end_source.type.width) - 1
            if target_limit < source_max:
                array_length_valid = builder.icmp_unsigned(
                    '<=',
                    end_source,
                    ir.Constant(end_source.type, target_limit),
                )
                valid_range = builder.and_(valid_range, array_length_valid)
        builder.cbranch(valid_range, step_valid_block, range_invalid_block)

        invalid_builder = ir.IRBuilder(range_invalid_block)
        trap = self.module.globals.get('llvm.trap')
        if trap is None:
            trap = ir.Function(
                self.module,
                ir.FunctionType(ir.VoidType(), []),
                name='llvm.trap',
            )
        invalid_builder.call(trap, [])
        invalid_builder.unreachable()

        use_ssa_iterator = (
            self._optimization_profile in {'prod', 'high'}
            and not self._iterator_address_is_taken(body, name)
        )
        valid_builder = ir.IRBuilder(step_valid_block)
        iterator = None
        if not use_ssa_iterator:
            iterator = valid_builder.alloca(iterator_type, name=f'{name}.addr')
            if self.type_registry is not None:
                iterator.align = self.type_registry.abi_alignment(iterator_type)
            valid_builder.store(start, iterator)
        valid_builder.branch(condition_block)

        condition_builder = ir.IRBuilder(condition_block)
        if use_ssa_iterator:
            current = condition_builder.phi(iterator_type, name=name)
            current.add_incoming(start, step_valid_block)
        else:
            current = condition_builder.load(iterator)
        condition = condition_builder.icmp_unsigned('<', current, end)
        condition_builder.cbranch(condition, body_block, after_block)

        body_builder = ir.IRBuilder(body_block)
        body_values = dict(values)
        body_values[name] = current if use_ssa_iterator else iterator
        self._loop_targets.append((after_block, step_block))
        try:
            self._emit_body(body, body_builder, body_values, function, symbol)
        finally:
            self._loop_targets.pop()
        if body_builder.block.terminator is None:
            body_builder.branch(step_block)

        step_builder = ir.IRBuilder(step_block)
        if not use_ssa_iterator:
            current = step_builder.load(iterator)
        # The range is half-open. If the next mathematical value reaches or
        # exceeds `end`, leave the loop without materialising an overflowing
        # unsigned value. This also makes ranges ending at UINT_MAX safe.
        reaches_end = step_builder.icmp_unsigned('>=', step, end)
        remaining = step_builder.sub(end, step)
        reaches_end = step_builder.or_(
            reaches_end,
            step_builder.icmp_unsigned('>=', current, remaining),
        )
        step_builder.cbranch(reaches_end, after_block, update_block)

        update_builder = ir.IRBuilder(update_block)
        if not use_ssa_iterator:
            current = update_builder.load(iterator)
        updated = update_builder.add(current, step)
        if use_ssa_iterator:
            current.add_incoming(updated, update_block)
        else:
            update_builder.store(updated, iterator)
        update_builder.branch(condition_block)

        builder.position_at_end(after_block)

    @classmethod
    def _branch_children(cls, node: object) -> list[object]:
        branches: list[object] = []
        for child in cls._children(node):
            if isinstance(child, list):
                branches.extend(cls._children(child))
            else:
                branches.append(child)
        return branches

    def _emit_if(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
        function: ir.Function,
        symbol: FunctionSymbol,
    ) -> None:
        branches: list[tuple[object, object]] = []
        else_body = None
        for child in self._branch_children(node):
            name = getattr(child, 'name', None)
            if name == 'IF_SIGNATURE':
                branches.append((child, None))
            elif name == 'ELIF':
                signature = next(
                    (
                        item for item in self._children(child)
                        if getattr(item, 'name', None) == 'ELIF_SIGNATURE'
                    ),
                    None,
                )
                body = self._statement_body(child)
                if signature is None or body is None:
                    raise FunctionEmissionError('El elif no tiene firma o cuerpo')
                branches.append((signature, body))
            elif name == 'STATEMENT_BODY' and branches:
                signature, body = branches[-1]
                if body is None:
                    branches[-1] = (signature, child)
            elif name == 'ELSE':
                else_body = self._statement_body(child)

        if not branches:
            raise FunctionEmissionError('El if no tiene ninguna rama')

        merge_block = function.append_basic_block(name='if.end')
        merge_reachable = False
        current_builder = builder

        for signature, body in branches:
            if body is None:
                raise FunctionEmissionError('El if no tiene cuerpo')
            true_block = function.append_basic_block(name='if.body')
            next_block = function.append_basic_block(name='if.next')
            condition = self._compile_condition(
                signature,
                current_builder,
                values,
                require_bool=True,
                condition_kind='if',
            )
            current_builder.cbranch(condition, true_block, next_block)

            body_builder = ir.IRBuilder(true_block)
            self._emit_body(body, body_builder, dict(values), function, symbol)
            if body_builder.block.terminator is None:
                body_builder.branch(merge_block)
                merge_reachable = True

            current_builder = ir.IRBuilder(next_block)

        if else_body is not None:
            else_block = function.append_basic_block(name='else.body')
            current_builder.branch(else_block)
            else_builder = ir.IRBuilder(else_block)
            self._emit_body(else_body, else_builder, dict(values), function, symbol)
            if else_builder.block.terminator is None:
                else_builder.branch(merge_block)
                merge_reachable = True
        else:
            current_builder.branch(merge_block)
            merge_reachable = True

        builder.position_at_end(merge_block)
        if not merge_reachable:
            builder.unreachable()

    def _emit_while(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
        function: ir.Function,
        symbol: FunctionSymbol,
    ) -> None:
        signature = next(
            (
                child for child in self._children(node)
                if getattr(child, 'name', None) == 'WHILE_SIGNATURE'
            ),
            None,
        )
        body = self._statement_body(node)
        if signature is None or body is None:
            raise FunctionEmissionError('El while no tiene firma o cuerpo')

        condition_block = function.append_basic_block(name='while.cond')
        body_block = function.append_basic_block(name='while.body')
        after_block = function.append_basic_block(name='while.end')
        builder.branch(condition_block)

        condition_builder = ir.IRBuilder(condition_block)
        condition = self._compile_condition(
            signature,
            condition_builder,
            values,
            require_bool=True,
            condition_kind='while',
        )
        condition_builder.cbranch(condition, body_block, after_block)

        body_builder = ir.IRBuilder(body_block)
        self._loop_targets.append((after_block, condition_block))
        try:
            self._emit_body(body, body_builder, dict(values), function, symbol)
        finally:
            self._loop_targets.pop()
        if body_builder.block.terminator is None:
            body_builder.branch(condition_block)

        builder.position_at_end(after_block)

    def _emit_body(
        self,
        body: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
        function: ir.Function,
        symbol: FunctionSymbol,
    ) -> None:
        for child in self._children(body):
            if builder.block.terminator is not None:
                break
            if isinstance(child, list):
                self._emit_body(child, builder, values, function, symbol)
                continue
            child_value = self._token_value(child)
            if child_value is None:
                child_value = getattr(child, 'value', None)
            if child_value == 'pass':
                continue
            if child_value in {'break', 'continue'}:
                if not self._loop_targets:
                    raise FunctionEmissionError(
                        f'{child_value} solo puede usarse dentro de un bucle'
                    )
                target = (
                    self._loop_targets[-1][0]
                    if child_value == 'break'
                    else self._loop_targets[-1][1]
                )
                builder.branch(target)
                continue
            name = getattr(child, 'name', None)
            if name == 'VAR':
                self._emit_local_declaration(child, builder, values)
            elif name == 'GLOBAL':
                # ``global`` is a compile-time visibility declaration.
                # Storage is already represented by the module global.
                continue
            elif name == 'VAR_ASSIGNATION':
                self._emit_assignment(child, builder, values, symbol)
            elif name == 'DEL':
                self._emit_deletion(child, builder, values)
            elif name == 'RETURN':
                self._emit_return(child, builder, values)
            elif name == 'CALL':
                self._compile_call(child, builder, values)
            elif name == 'FOR':
                self._emit_for(child, builder, values, function, symbol)
            elif name == 'IF':
                self._emit_if(child, builder, values, function, symbol)
            elif name == 'WHILE':
                self._emit_while(child, builder, values, function, symbol)
            elif name in {'FUNCTION_BODY', 'STATEMENT_BODY'}:
                self._emit_body(child, builder, values, function, symbol)
            elif name is not None:
                raise FunctionEmissionError(
                    f'La sentencia {name} no tiene emision LLVM en esta fase'
                )

    def _emit_function(
        self,
        symbol: FunctionSymbol,
        function: ir.Function,
    ) -> None:
        self._active_function_symbol = symbol
        if symbol.body_node is None:
            raise FunctionEmissionError(
                f'La funcion {symbol.name} no tiene cuerpo emitible'
            )
        block = function.append_basic_block(name='entry')
        builder = ir.IRBuilder(block)
        variables = getattr(symbol, 'local_variables', None)
        if variables is None:
            variables = symbol.scope.namespace if symbol.scope else {}
        self._active_specs = {
            name: variable.type_spec
            for name, variable in variables.items()
            if getattr(variable, 'type_spec', None) is not None
        }
        self._active_specs.update(getattr(symbol, 'loop_iterators', {}))
        if symbol.is_method and not symbol.is_static and symbol.owner_type:
            self._active_specs['self'] = TypeSpec(symbol.owner_type)
        self._active_values = {
            name: getattr(variable, 'value_info', None)
            for name, variable in variables.items()
            if getattr(variable, 'value_info', None) is not None
        }
        self._loop_targets.clear()
        values = self._prepare_values(symbol, builder, list(function.args))
        self._emit_body(symbol.body_node, builder, values, function, symbol)
        if builder.block.terminator is None and (
            symbol.signature.return_type.name == 'Never'
            and symbol.signature.return_type.pointer_level == 0
            and symbol.signature.return_type.array_depth == 0
        ):
            builder.unreachable()
        if builder.block.terminator is None:
            raise FunctionEmissionError(
                f'La funcion {symbol.name} no termina con return'
            )

    def emit_main(self, symbol: FunctionSymbol) -> None:
        self._active_function_symbol = symbol
        if symbol.signature.parameters:
            raise FunctionEmissionError(
                'El entrypoint main no puede tener parametros'
            )
        if (
            symbol.signature.return_type.name != 'int32'
            or symbol.signature.return_type.pointer_level
            or symbol.signature.return_type.array_depth
        ):
            raise FunctionEmissionError(
                'El entrypoint main debe retornar int32'
            )
        if (
            symbol.return_asm_node is None
            and len(symbol.return_values) != 1
            and not symbol.body_terminates
        ):
            raise FunctionEmissionError(
                'El entrypoint main requiere un unico return int32'
            )
        if symbol.body_node is None:
            raise FunctionEmissionError(
                'El entrypoint main requiere un cuerpo emitible'
            )

        int_type = ir.IntType(32)
        source_type = ir.FunctionType(int_type, [])
        source_function = ir.Function(
            self.module,
            source_type,
            name='__bagron_main',
        )
        self._apply_function_attributes(
            source_function,
            symbol,
            self._optimization_profile,
        )
        if symbol.return_asm_node is not None:
            native_type = ir.FunctionType(int_type, [])
            native_function = ir.Function(self.module, native_type, name='main')
            native_block = native_function.append_basic_block(name='entry')
            native_builder = ir.IRBuilder(native_block)
            result = native_builder.call(source_function, [])
            native_builder.ret(result)
            return

        source_function.linkage = 'internal'
        source_block = source_function.append_basic_block(name='entry')
        source_builder = ir.IRBuilder(source_block)
        variables = getattr(symbol, 'local_variables', None)
        if variables is None:
            variables = symbol.scope.namespace if symbol.scope else {}
        self._active_specs = {
            name: variable.type_spec
            for name, variable in variables.items()
            if getattr(variable, 'type_spec', None) is not None
        }
        self._active_specs.update(getattr(symbol, 'loop_iterators', {}))
        self._active_values = {
            name: getattr(variable, 'value_info', None)
            for name, variable in variables.items()
            if getattr(variable, 'value_info', None) is not None
        }
        self._loop_targets.clear()
        values = self._prepare_values(symbol, source_builder, [])
        self._emit_body(
            symbol.body_node,
            source_builder,
            values,
            source_function,
            symbol,
        )
        if source_builder.block.terminator is None:
            raise FunctionEmissionError(
                'El entrypoint main no termina con return'
            )

        native_type = ir.FunctionType(int_type, [])
        native_function = ir.Function(self.module, native_type, name='main')
        native_block = native_function.append_basic_block(name='entry')
        native_builder = ir.IRBuilder(native_block)
        result = native_builder.call(source_function, [])
        native_builder.ret(result)


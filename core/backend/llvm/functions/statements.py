from __future__ import annotations

from llvmlite import ir

from core.backend.llvm.types import (
    LLVMTypeError,
    constant_value,
    default_value,
    scalar_type,
    value_type,
)
from core.frontend.objects import FunctionSymbol
from core.frontend.tools.types import (
    FOR_ITERATOR_TYPES,
    UNSIGNED_INTEGER_TYPES,
    target_iteration_limit,
)

from .errors import FunctionEmissionError


class StatementEmitterMixin:
    """LLVM emission for declarations, control flow, and function bodies."""

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

        place = self._compile_place(target, builder, values)

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
                variable = symbol.scope.resolve(name)
                type_spec = getattr(variable, 'type_spec', None)
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

    def _prepare_values(
        self,
        symbol: FunctionSymbol,
        builder: ir.IRBuilder,
        arguments: list[ir.Argument],
    ) -> dict[str, ir.Value]:
        values: dict[str, ir.Value] = {}
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
            )
        }
        for name, variable in scope.namespace.items():
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
                ir.Constant(local_type, None)
                if name in chain_parameters or name in array_parameters
                else default_value(
                    variable.type_spec,
                    getattr(variable, 'value_info', None),
                    self.type_registry,
                )
            )
            self._store_address(
                initial_value,
                pointer,
                builder,
                alignment=pointer.align,
                volatile=self._aggregate_volatile(local_type),
            )

        for parameter, argument in zip(symbol.signature.parameters, arguments):
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
        if (
            type_spec.name not in FOR_ITERATOR_TYPES
            or type_spec.pointer_level
            or type_spec.array_depth
        ):
            raise FunctionEmissionError(
                f'El iterador {name} debe tener exactamente un tipo '
                'uint8/uint16/uint32/uint64'
            )
        iterator_type = scalar_type(type_spec)
        if not isinstance(iterator_type, ir.IntType):
            raise FunctionEmissionError(f'El iterador {name} no es uint*')

        range_values = [
            child for child in self._children(signature)
            if getattr(child, 'name', None) == 'VALUE'
        ]
        if len(range_values) != 3:
            raise FunctionEmissionError(
                f'El rango de {name} debe tener start, end y step'
            )

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
        target_limit = min(
            target_iteration_limit(self._pointer_size),
            (1 << iterator_type.width) - 1,
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

        valid_builder = ir.IRBuilder(step_valid_block)
        iterator = valid_builder.alloca(iterator_type, name=f'{name}.addr')
        if self.type_registry is not None:
            iterator.align = self.type_registry.abi_alignment(iterator_type)
        valid_builder.store(start, iterator)
        valid_builder.branch(condition_block)

        condition_builder = ir.IRBuilder(condition_block)
        current = condition_builder.load(iterator)
        condition = condition_builder.icmp_unsigned('<', current, end)
        condition_builder.cbranch(condition, body_block, after_block)

        body_builder = ir.IRBuilder(body_block)
        body_values = dict(values)
        body_values[name] = iterator
        self._loop_targets.append((after_block, step_block))
        try:
            self._emit_body(body, body_builder, body_values, function, symbol)
        finally:
            self._loop_targets.pop()
        if body_builder.block.terminator is None:
            body_builder.branch(step_block)

        step_builder = ir.IRBuilder(step_block)
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
        current = update_builder.load(iterator)
        updated = update_builder.add(current, step)
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
        current_builder = builder

        for signature, body in branches:
            if body is None:
                raise FunctionEmissionError('El if no tiene cuerpo')
            true_block = function.append_basic_block(name='if.body')
            next_block = function.append_basic_block(name='if.next')
            condition = self._compile_condition(signature, current_builder, values)
            current_builder.cbranch(condition, true_block, next_block)

            body_builder = ir.IRBuilder(true_block)
            self._emit_body(body, body_builder, dict(values), function, symbol)
            if body_builder.block.terminator is None:
                body_builder.branch(merge_block)

            current_builder = ir.IRBuilder(next_block)

        if else_body is not None:
            else_block = function.append_basic_block(name='else.body')
            current_builder.branch(else_block)
            else_builder = ir.IRBuilder(else_block)
            self._emit_body(else_body, else_builder, dict(values), function, symbol)
            if else_builder.block.terminator is None:
                else_builder.branch(merge_block)
        else:
            current_builder.branch(merge_block)

        builder.position_at_end(merge_block)

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
        condition = self._compile_condition(signature, condition_builder, values)
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
            elif name == 'VAR_ASSIGNATION':
                self._emit_assignment(child, builder, values, symbol)
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
        self._active_specs = {
            name: variable.type_spec
            for name, variable in (symbol.scope.namespace.items() if symbol.scope else ())
            if getattr(variable, 'type_spec', None) is not None
        }
        self._active_specs.update(getattr(symbol, 'loop_iterators', {}))
        self._active_values = {
            name: getattr(variable, 'value_info', None)
            for name, variable in (symbol.scope.namespace.items() if symbol.scope else ())
            if getattr(variable, 'value_info', None) is not None
        }
        self._loop_targets.clear()
        values = self._prepare_values(symbol, builder, list(function.args))
        self._emit_body(symbol.body_node, builder, values, function, symbol)
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
        if symbol.return_asm_node is None and len(symbol.return_values) != 1:
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
        self._active_specs = {
            name: variable.type_spec
            for name, variable in (symbol.scope.namespace.items() if symbol.scope else ())
            if getattr(variable, 'type_spec', None) is not None
        }
        self._active_specs.update(getattr(symbol, 'loop_iterators', {}))
        self._active_values = {
            name: getattr(variable, 'value_info', None)
            for name, variable in (symbol.scope.namespace.items() if symbol.scope else ())
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


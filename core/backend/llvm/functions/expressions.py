from __future__ import annotations

from llvmlite import ir

from .errors import FunctionEmissionError


class ExpressionEmitterMixin:
    """LLVM emission for expressions, addresses, and calls."""

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

    def _compile_address(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        """Emit the address represented by an lvalue/access expression."""
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
            return self._compile_address(children[0], builder, values)

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
                return self._checked_pointer(value, builder)
            return self._compile_address(inner, builder, values)

        if getattr(current, 'name', None) == 'DEREF_TARGET':
            children = self._children(current)
            if not children:
                raise FunctionEmissionError('La desreferenciacion esta vacia')
            value = self._compile_expression(children[0], builder, values)
            if not isinstance(value.type, ir.PointerType):
                raise FunctionEmissionError('La desreferenciacion requiere un puntero')
            return self._checked_pointer(value, builder)

        if getattr(current, 'name', None) == 'DEREF_ASSIGN_TARGET':
            children = self._children(current)
            if not children:
                raise FunctionEmissionError('La desreferenciacion esta vacia')
            value = self._compile_expression(children[0], builder, values)
            if not isinstance(value.type, ir.PointerType):
                raise FunctionEmissionError('La desreferenciacion requiere un puntero')
            return self._checked_pointer(value, builder)

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

            address = self._compile_address(primary, builder, values)
            for suffix in suffixes:
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
                    pointee = address.type.pointee
                    if self._is_array_descriptor_type(pointee):
                        descriptor = builder.load(address)
                        data = builder.extract_value(descriptor, 0)
                        address = builder.gep(data, [index], inbounds=False)
                    elif isinstance(pointee, ir.PointerType):
                        address = self._checked_pointer(
                            builder.load(address),
                            builder,
                        )
                        address = builder.gep(address, [index], inbounds=False)
                    elif isinstance(pointee, ir.ArrayType):
                        address = builder.gep(
                            address,
                            [ir.Constant(ir.IntType(32), 0), index],
                            inbounds=False,
                        )
                    else:
                        # The semantic pass guarantees that this is a pointer
                        # access.  A scalar GEP keeps raw-pointer indexing
                        # available for future pointer arithmetic without
                        # inventing a second address representation.
                        address = builder.gep(address, [index], inbounds=False)
                    continue
                if name == 'MEMBER_ACCESS':
                    member = self._identifier(suffix)
                    pointee = address.type.pointee
                    if not isinstance(pointee, ir.IdentifiedStructType):
                        raise FunctionEmissionError(
                            'El acceso a miembros requiere un struct LLVM'
                        )
                    field_index = (
                        self.type_registry.field_index(pointee.name, member or '')
                        if self.type_registry is not None
                        else None
                    )
                    if field_index is None:
                        raise FunctionEmissionError(
                            f'El miembro {member or "<anonimo>"} no existe en '
                            f'{pointee.name}'
                        )
                    address = builder.gep(
                        address,
                        [
                            ir.Constant(ir.IntType(32), 0),
                            ir.Constant(ir.IntType(32), field_index),
                        ],
                        inbounds=False,
                    )
            return address

        kind = self._token_kind(current)
        value = self._token_value(current)
        if kind == 'IDENT':
            name = str(value)
            if name in values:
                return values[name]
            global_value = self.module.globals.get(name)
            if isinstance(global_value, ir.GlobalVariable):
                return global_value
            raise FunctionEmissionError(
                f'La variable {name} no tiene almacenamiento LLVM'
            )

        raise FunctionEmissionError('La expresion no es direccionable')

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
                elif isinstance(left.type, ir.IntType):
                    right = self._coerce_int(
                        right,
                        left.type,
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
                    'SLASH': builder.sdiv,
                    'PERCENT': builder.srem,
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
                        return ir.Constant(ir.IntType(32), pointee.count)
                    if self._is_array_descriptor_type(pointee):
                        descriptor = builder.load(address)
                        return builder.extract_value(descriptor, 1)
                    raise FunctionEmissionError(
                        'La longitud solo puede obtenerse de un array'
                    )
                address = self._compile_address(current, builder, values)
                return builder.load(address)

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
                return builder.load(self._checked_pointer(value, builder))
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
            chain_pointer = (
                self._active_specs.get(name) is not None
                and self._active_specs[name].name == 'chain'
                and isinstance(expected_type, ir.PointerType)
                and isinstance(expected_type.pointee, ir.IntType)
                and expected_type.pointee.width == 8
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
                return builder.load(result)
            if isinstance(result, ir.GlobalVariable):
                return builder.load(result)
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
        if isinstance(pointee, ir.PointerType):
            pointer = builder.load(address)
        elif isinstance(pointee, ir.ArrayType):
            pointer = builder.gep(
                address,
                [
                    ir.Constant(ir.IntType(32), 0),
                    ir.Constant(ir.IntType(32), 0),
                ],
                inbounds=True,
            )
        else:
            raise FunctionEmissionError(
                'El argumento no es un array compatible'
            )
        if pointer.type != target_type:
            raise FunctionEmissionError(
                'El elemento del array no coincide con el parametro de la funcion'
            )
        return pointer

    def _compile_array_length(
        self,
        argument: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        address = self._compile_address(argument, builder, values)
        pointee = address.type.pointee
        if not isinstance(pointee, ir.ArrayType):
            raise FunctionEmissionError(
                'Len_t requiere un array con tamano conocido en compilacion'
            )
        return ir.Constant(ir.IntType(64), pointee.count)

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

    def _compile_array_size(
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
                'Size_t requiere un array con tamano conocido en compilacion'
            )
        return ir.Constant(
            ir.IntType(64),
            self._llvm_type_size(pointee, self._pointer_size),
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
            return self._compile_array_size(
                argument,
                source_type,
                builder,
                values,
            )
        return ir.Constant(
            ir.IntType(64),
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
                        self._compile_array_length(source, builder, values)
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
            if parameter.type_spec.array_depth and any(
                length is None for length in parameter.type_spec.array_lengths
            ):
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
                    )
                )
            argument_index += 1
            llvm_index += 1
        return builder.call(callee, compiled)


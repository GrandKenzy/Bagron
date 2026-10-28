from __future__ import annotations

from llvmlite import ir

from .errors import FunctionEmissionError


class ExpressionEmitterMixin:
    """LLVM emission for expressions, addresses, and calls."""

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
                    if isinstance(pointee, ir.PointerType):
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
                return builder.neg(operand)
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

            if left.type != right.type:
                if not isinstance(left.type, ir.IntType):
                    raise FunctionEmissionError(
                        'Los operandos aritmeticos deben ser enteros'
                    )
                right = self._coerce_int(
                    right,
                    left.type,
                    builder,
                    signed=not unsigned,
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
                compare = (
                    builder.icmp_unsigned
                    if unsigned
                    else builder.icmp_signed
                )
                return compare(predicates[operator], left, right)

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
        if kind == 'NUMBER':
            return ir.Constant(ir.IntType(32), int(value))
        if kind == 'BOOL':
            return ir.Constant(ir.IntType(1), int(str(value).lower() == 'true'))
        if kind == 'NULL':
            return ir.Constant(ir.IntType(8).as_pointer(), None)
        if kind == 'STRING':
            if not isinstance(value, str):
                raise FunctionEmissionError('El literal de char no es valido')
            try:
                data = value.encode('ascii')
            except UnicodeEncodeError as error:
                raise FunctionEmissionError(
                    'Un literal de char solo puede contener ASCII'
                ) from error
            if len(data) != 1:
                raise FunctionEmissionError(
                    'Un literal usado como char o byte debe contener un byte'
                )
            return ir.Constant(ir.IntType(8), data[0])
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
        if len(argument_items) != len(callee.args):
            raise FunctionEmissionError(
                f'La funcion {name or "<anonima>"} recibio un numero invalido '
                'de argumentos'
            )
        compiled = [
            self._coerce_value(
                self._compile_expression(argument, builder, values),
                callee.args[index].type,
                builder,
            )
            for index, argument in enumerate(argument_items)
        ]
        return builder.call(callee, compiled)


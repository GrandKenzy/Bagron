from __future__ import annotations

from dataclasses import dataclass

from llvmlite import ir

from core.frontend.objects import TypeSpec
from core.frontend.tools.types import (
    MAGIC_BINARY_OPERATORS,
    MAGIC_UNARY_OPERATORS,
)

from ..errors import FunctionEmissionError
from .memory import _MemoryPlace



class ValueExpressionMixin:
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
            if (
                operator == 'PLUS'
                and self._is_buffer_descriptor_type(left.type)
                and self._is_buffer_descriptor_type(right.type)
            ):
                return self._emit_buffer_concat(left, right, builder)
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
                if result is None:
                    global_name = self._global_llvm_name(name)
                    if global_name in self.module.globals:
                        result = self.module.globals[global_name]
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

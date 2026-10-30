from __future__ import annotations

from dataclasses import dataclass

from llvmlite import ir

from core.frontend.objects import TypeSpec
from core.frontend.tools.types import (
    MAGIC_BINARY_OPERATORS,
    MAGIC_UNARY_OPERATORS,
)

from ..errors import FunctionEmissionError



class OperatorExpressionMixin:
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

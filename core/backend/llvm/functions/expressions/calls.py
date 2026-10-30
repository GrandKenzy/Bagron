from __future__ import annotations

from dataclasses import dataclass

from llvmlite import ir

from core.frontend.objects import TypeSpec
from core.frontend.tools.types import (
    MAGIC_BINARY_OPERATORS,
    MAGIC_UNARY_OPERATORS,
)

from ..errors import FunctionEmissionError



class CallExpressionMixin:
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
        # Len_t/Size_t parameters are emitted directly as immutable SSA
        # arguments; older storage-backed values still use their alloca.
        if getattr(pointer, 'opname', None) == 'alloca':
            return builder.load(pointer)
        return pointer

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
        if getattr(source_spec, 'name', None) == 'buffer':
            forwarded = self._compile_forwarded_expansion(
                argument,
                is_length=True,
                builder=builder,
                values=values,
            )
            if forwarded is not None:
                return forwarded
            descriptor = self._compile_expression(argument, builder, values)
            _, length = self._buffer_data_and_length(descriptor, builder)
            return length
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
            return value_type.count * CallExpressionMixin._llvm_type_size(
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
                or getattr(parameter, 'is_region', False)
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
                or getattr(parameter, 'is_region', False)
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
        source_llvm_index = 0
        for index, parameter in enumerate(parameters):
            if getattr(parameter, 'is_region', False):
                continue
            if not (
                getattr(parameter, 'is_length', False)
                or getattr(parameter, 'is_size', False)
                or getattr(parameter, 'is_receiver', False)
            ):
                source_llvm_indices[parameter.name] = source_llvm_index
            source_llvm_index += 1
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

            if getattr(parameter, 'is_region', False):
                # Region_t is immutable provenance metadata, not a runtime
                # argument. Its source slot is materialized as a local zero
                # only when the function body refers to the marker.
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

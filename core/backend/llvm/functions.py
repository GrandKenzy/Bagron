from __future__ import annotations

from typing import TYPE_CHECKING

from llvmlite import ir

from core.backend.llvm.types import (
    LLVMTypeError,
    LLVMTypeRegistry,
    constant_value,
    llvm_type,
    scalar_type,
    value_type,
    zero_value,
)
from core.frontend.objects import FunctionSymbol, TypeSpec
from core.frontend.tools.types import UNSIGNED_INTEGER_TYPES

if TYPE_CHECKING:
    from core.storage import Storage


class FunctionEmissionError(ValueError):
    """Raised when a supported function cannot be represented in LLVM yet."""


class FunctionEmitter:
    """Emit integer functions, calls, arithmetic and the native entrypoint."""

    def __init__(
        self,
        module: ir.Module,
        type_registry: LLVMTypeRegistry | None = None,
    ):
        self.module = module
        self.type_registry = type_registry
        self._functions: dict[str, ir.Function] = {}
        self._active_specs: dict[str, TypeSpec] = {}
        self._active_values: dict[str, object] = {}
        self._loop_targets: list[tuple[ir.Block, ir.Block]] = []

    def emit_storage(self, storage: Storage) -> None:
        for symbol in storage.functions.values():
            if (
                symbol.name != 'main'
                and symbol.name not in self._functions
                and self._supports_int_function(symbol)
            ):
                self._functions[symbol.name] = ir.Function(
                    self.module,
                    self._function_type(symbol),
                    name=symbol.name,
                )

        emitted: set[str] = set()
        for symbol in storage.functions.values():
            if (
                symbol.name != 'main'
                and symbol.name in self._functions
                and symbol.name not in emitted
            ):
                if symbol.return_asm_node is None:
                    self._emit_function(symbol, self._functions[symbol.name])
                emitted.add(symbol.name)

        for alias, target in storage.function_aliases.items():
            function = self._functions.get(target)
            if function is not None:
                self._functions[alias] = function

        main = storage.functions.get('main')
        if main is not None:
            self.emit_main(main)

    def _supports_int_function(self, symbol: FunctionSymbol) -> bool:
        try:
            return_type = llvm_type(
                symbol.signature.return_type,
                type_registry=self.type_registry,
            )
            if not self._supports_runtime_type(return_type):
                return False

            for parameter in symbol.signature.parameters:
                parameter_type = llvm_type(
                    parameter.type_spec,
                    type_registry=self.type_registry,
                )
                if not self._supports_runtime_type(parameter_type):
                    return False
        except (AttributeError, TypeError, ValueError):
            return False

        if symbol.scope is None:
            return True

        try:
            for variable in symbol.scope.namespace.values():
                variable_type = value_type(
                    variable.type_spec,
                    getattr(variable, 'value_info', None),
                    self.type_registry,
                )
                if not self._supports_runtime_type(variable_type):
                    return False
            return True
        except (AttributeError, TypeError, ValueError, LLVMTypeError):
            return False

    @staticmethod
    def _supports_runtime_type(value_type_: ir.Type) -> bool:
        """Return whether the first-stage emitter can store/load a value."""
        if isinstance(value_type_, (ir.IntType, ir.PointerType)):
            return True
        if isinstance(value_type_, ir.ArrayType):
            return FunctionEmitter._supports_runtime_type(value_type_.element)
        # Identified structs are legal storage for member access.  Keep this
        # name-based check compatible with llvmlite versions that expose the
        # literal/identified classes differently.
        return value_type_.__class__.__name__ in {
            'IdentifiedStructType',
            'LiteralStructType',
        }

    def _function_type(self, symbol: FunctionSymbol) -> ir.FunctionType:
        try:
            parameters = [
                llvm_type(parameter.type_spec, type_registry=self.type_registry)
                for parameter in symbol.signature.parameters
            ]
            return_type = llvm_type(
                symbol.signature.return_type,
                type_registry=self.type_registry,
            )
        except LLVMTypeError as error:
            raise FunctionEmissionError(str(error)) from error
        return ir.FunctionType(return_type, parameters)

    @staticmethod
    def _children(node: object) -> list[object]:
        if isinstance(node, list):
            return list(node)
        nodes = getattr(node, 'nodes', None)
        if nodes is not None:
            return list(nodes)
        items = getattr(node, 'items', None)
        if items is not None:
            return list(items)
        return []

    @staticmethod
    def _token_kind(node: object) -> str | None:
        token = getattr(node, 'token', None)
        token = getattr(token, 'token', token)
        return getattr(token, 'name', None)

    @staticmethod
    def _token_value(node: object) -> object | None:
        token = getattr(node, 'token', None)
        return getattr(token, 'value', None)

    @classmethod
    def _identifier(cls, node: object) -> str | None:
        if cls._token_kind(node) == 'IDENT':
            return str(cls._token_value(node))
        for child in cls._children(node):
            found = cls._identifier(child)
            if found is not None:
                return found
        return None

    @classmethod
    def _unwrap(cls, node: object) -> object:
        current = node
        while (
            getattr(current, 'name', None) in ('VALUE', 'POSTFIX_EXPR', 'PRIMARY')
            and len(cls._children(current)) == 1
        ):
            current = cls._children(current)[0]
        return current

    def _expression_is_unsigned(self, node: object) -> bool:
        name = self._identifier(node)
        if name is None:
            return False
        spec = self._active_specs.get(name)
        return spec is not None and spec.name in UNSIGNED_INTEGER_TYPES

    @staticmethod
    def _condition_value(node: object) -> object | None:
        condition = next(
            (
                child for child in FunctionEmitter._children(node)
                if getattr(child, 'name', None) == 'CONDITION'
            ),
            None,
        )
        if condition is None:
            return None
        return next(
            (
                child for child in FunctionEmitter._children(condition)
                if getattr(child, 'name', None) == 'VALUE'
            ),
            None,
        )

    def _compile_condition(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        value_node = self._condition_value(node)
        if value_node is None:
            raise FunctionEmissionError('La condicion no tiene una expresion')
        result = self._compile_expression(value_node, builder, values)
        if isinstance(result.type, ir.IntType):
            if result.type.width == 1:
                return result
            return builder.icmp_unsigned(
                '!=',
                result,
                ir.Constant(result.type, 0),
            )
        raise FunctionEmissionError(
            'La condicion debe producir bool o un entero escalar'
        )

    @staticmethod
    def _coerce_int(
        value: ir.Value,
        target_type: ir.IntType,
        builder: ir.IRBuilder,
        signed: bool = True,
    ) -> ir.Value:
        if value.type == target_type:
            return value
        if isinstance(value.type, ir.IntType):
            if value.type.width < target_type.width:
                return (
                    builder.sext(value, target_type)
                    if signed
                    else builder.zext(value, target_type)
                )
            return builder.trunc(value, target_type)
        raise FunctionEmissionError('Se esperaba un valor entero en LLVM')

    def _coerce_value(
        self,
        value: ir.Value,
        target_type: ir.Type,
        builder: ir.IRBuilder,
        signed: bool = True,
    ) -> ir.Value:
        if value.type == target_type:
            return value
        if isinstance(target_type, ir.IntType):
            return self._coerce_int(value, target_type, builder, signed)
        if isinstance(target_type, ir.PointerType) and isinstance(
            value.type,
            ir.PointerType,
        ):
            return builder.bitcast(value, target_type)
        raise FunctionEmissionError(
            f'No se puede convertir {value.type} a {target_type} en LLVM'
        )

    def _checked_pointer(
        self,
        value: ir.Value,
        builder: ir.IRBuilder,
    ) -> ir.Value:
        if not isinstance(value.type, ir.PointerType):
            raise FunctionEmissionError('Se esperaba un puntero en LLVM')

        function = builder.function
        if function is None:
            raise FunctionEmissionError('El puntero no pertenece a una funcion LLVM')

        block_id = len(function.blocks)
        nonnull = function.append_basic_block(name=f'deref.ok.{block_id}')
        null = function.append_basic_block(name=f'deref.null.{block_id}')
        condition = builder.icmp_unsigned(
            '!=',
            value,
            ir.Constant(value.type, None),
        )
        builder.cbranch(condition, nonnull, null)

        null_builder = ir.IRBuilder(null)
        trap = self.module.globals.get('llvm.trap')
        if trap is None:
            trap = ir.Function(
                self.module,
                ir.FunctionType(ir.VoidType(), []),
                name='llvm.trap',
            )
        null_builder.call(trap, [])
        null_builder.unreachable()

        builder.position_at_end(nonnull)
        return value

    @staticmethod
    def _coerce_condition_value(
        value: ir.Value,
        builder: ir.IRBuilder,
    ) -> ir.Value:
        if not isinstance(value.type, ir.IntType):
            raise FunctionEmissionError(
                'La condicion debe producir bool o un entero escalar'
            )
        if value.type.width == 1:
            return value
        return builder.icmp_unsigned(
            '!=',
            value,
            ir.Constant(value.type, 0),
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
                compiled = [
                    self._coerce_value(
                        self._compile_expression(argument, builder, values),
                        callee.args[index].type,
                        builder,
                    )
                    for index, argument in enumerate(argument_items)
                ]
                return builder.call(callee, compiled)
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
            result = self._compile_expression(value_node, builder, values)
        result = self._coerce_value(result, pointer.type.pointee, builder)
        builder.store(result, pointer)

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

        pointer = self._compile_address(target, builder, values)

        value_node = self._assignment_value(node)
        operator = self._assignment_operator(node)
        if value_node is None or operator is None:
            raise FunctionEmissionError('La asignacion local es invalida')

        target_type = pointer.type.pointee
        right = self._coerce_value(
            self._compile_expression(value_node, builder, values),
            target_type,
            builder,
        )
        if operator == '=':
            result = right
        else:
            left = builder.load(pointer)
            unsigned = False
            if symbol.scope is not None and name is not None:
                variable = symbol.scope.resolve(name)
                type_spec = getattr(variable, 'type_spec', None)
                unsigned = getattr(type_spec, 'name', None) in UNSIGNED_INTEGER_TYPES
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
        builder.store(result, pointer)

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

        for name, variable in scope.namespace.items():
            try:
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
            values[name] = pointer
            builder.store(ir.Constant(local_type, None), pointer)

        for parameter, argument in zip(symbol.signature.parameters, arguments):
            pointer = values.get(parameter.name)
            if pointer is None:
                raise FunctionEmissionError(
                    f'El parametro {parameter.name} no tiene almacenamiento LLVM'
                )
            argument.name = parameter.name
            builder.store(
                self._coerce_value(argument, pointer.type.pointee, builder),
                pointer,
            )
        return values

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
        if return_node is None:
            raise FunctionEmissionError('El return necesita un valor entero')
        result = self._compile_expression(return_node, builder, values)
        result = self._coerce_value(
            result,
            builder.function.function_type.return_type,
            builder,
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
        iterator_symbol = symbol.scope.resolve(name)
        type_spec = getattr(iterator_symbol, 'type_spec', None)
        if type_spec is None:
            raise FunctionEmissionError(f'No existe el iterador {name}')
        iterator_type = scalar_type(type_spec)
        if not isinstance(iterator_type, ir.IntType):
            raise FunctionEmissionError(f'El iterador {name} no es entero')
        signed = type_spec.name in {
            'int', 'int8', 'int16', 'int32', 'int64', 'Bint'
        }

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
            signed,
        )
        end = self._coerce_int(
            self._compile_expression(range_values[1], builder, values),
            iterator_type,
            builder,
            signed,
        )
        step = self._coerce_int(
            self._compile_expression(range_values[2], builder, values),
            iterator_type,
            builder,
            signed,
        )

        iterator = values.get(name)
        if iterator is None:
            iterator = builder.alloca(iterator_type, name=f'{name}.addr')
            values[name] = iterator
        builder.store(start, iterator)

        condition_block = function.append_basic_block(name='for.cond')
        body_block = function.append_basic_block(name='for.body')
        step_block = function.append_basic_block(name='for.step')
        after_block = function.append_basic_block(name='for.end')
        builder.branch(condition_block)

        condition_builder = ir.IRBuilder(condition_block)
        current = condition_builder.load(iterator)
        zero = ir.Constant(iterator_type, 0)
        positive = condition_builder.icmp_signed('>', step, zero)
        ascending = condition_builder.icmp_signed('<', current, end)
        descending = condition_builder.icmp_signed('>', current, end)
        condition = condition_builder.select(positive, ascending, descending)
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
        updated = step_builder.add(current, step)
        step_builder.store(updated, iterator)
        step_builder.branch(condition_block)

        builder.position_at_end(after_block)
        values[name] = iterator

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
        if symbol.signature.parameters:
            raise FunctionEmissionError(
                'El entrypoint main no puede tener parametros'
            )
        if (
            symbol.signature.return_type.name != 'int'
            or symbol.signature.return_type.pointer_level
            or symbol.signature.return_type.array_depth
        ):
            raise FunctionEmissionError(
                'El entrypoint main debe retornar int'
            )
        if symbol.return_asm_node is None and len(symbol.return_values) != 1:
            raise FunctionEmissionError(
                'El entrypoint main requiere un unico return int'
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


__all__ = ['FunctionEmissionError', 'FunctionEmitter']

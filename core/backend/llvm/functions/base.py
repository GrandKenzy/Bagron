from __future__ import annotations

from typing import TYPE_CHECKING

from llvmlite import ir

from core.backend.llvm.types import (
    LLVMTypeError,
    LLVMTypeRegistry,
    llvm_type,
    value_type,
)
from core.frontend.objects import FunctionSymbol, TypeSpec
from core.frontend.tools.types import UNSIGNED_INTEGER_TYPES

from .errors import FunctionEmissionError

if TYPE_CHECKING:
    from core.storage import Storage


class FunctionEmitterBase:
    """Shared state, AST helpers, and LLVM primitive operations."""

    def __init__(
        self,
        module: ir.Module,
        type_registry: LLVMTypeRegistry | None = None,
    ):
        self.module = module
        self.type_registry = type_registry
        self._functions: dict[str, ir.Function] = {}
        self._symbols: dict[str, FunctionSymbol] = {}
        self._active_specs: dict[str, TypeSpec] = {}
        self._active_values: dict[str, object] = {}
        self._global_values: dict[str, object] = {}
        self._active_function_symbol: FunctionSymbol | None = None
        self._loop_targets: list[tuple[ir.Block, ir.Block]] = []
        self._string_literals: dict[str, ir.GlobalVariable] = {}
        self._pointer_size = 8

    def _string_pointer(
        self,
        value: str,
        builder: ir.IRBuilder,
    ) -> ir.Value:
        global_value = self._string_literals.get(value)
        if global_value is None:
            data = value.encode('utf-8')
            byte_type = ir.IntType(8)
            array_type = ir.ArrayType(byte_type, len(data) + 1)
            initializer = ir.Constant(
                array_type,
                [ir.Constant(byte_type, byte) for byte in (*data, 0)],
            )
            global_value = ir.GlobalVariable(
                self.module,
                array_type,
                name=f'__bagron_string_{len(self._string_literals)}',
            )
            global_value.linkage = 'private'
            global_value.global_constant = True
            global_value.initializer = initializer
            self._string_literals[value] = global_value

        index_type = ir.IntType(32)
        return builder.gep(
            global_value,
            [ir.Constant(index_type, 0), ir.Constant(index_type, 0)],
            inbounds=True,
        )

    def emit_storage(self, storage: Storage) -> None:
        self._pointer_size = getattr(storage, 'pointer_size', 8)
        self._symbols = dict(storage.functions)
        self._global_values = {
            name: getattr(variable, 'value_info', None)
            for name, variable in storage.namespace.items()
            if getattr(variable, 'value_info', None) is not None
        }
        for symbol in storage.functions.values():
            if (
                symbol.name != 'main'
                and symbol.name not in self._functions
                and self._supports_function(symbol)
            ):
                function = ir.Function(
                    self.module,
                    self._function_type(symbol),
                    name=symbol.name,
                )
                if symbol.calling_convention:
                    function.calling_convention = symbol.calling_convention
                self._functions[symbol.name] = function

        emitted: set[str] = set()
        for symbol in storage.functions.values():
            if (
                symbol.name != 'main'
                and symbol.name in self._functions
                and symbol.name not in emitted
                and not symbol.is_external
            ):
                if symbol.return_asm_node is None:
                    self._emit_function(symbol, self._functions[symbol.name])
                emitted.add(symbol.name)

        for alias, target in storage.function_aliases.items():
            function = self._functions.get(target)
            if function is not None:
                self._functions[alias] = function
                symbol = self._symbols.get(target)
                if symbol is not None:
                    self._symbols[alias] = symbol

        main = storage.functions.get('main')
        if main is not None:
            self.emit_main(main)

    def _supports_function(self, symbol: FunctionSymbol) -> bool:
        try:
            return_type = llvm_type(
                symbol.signature.return_type,
                type_registry=self.type_registry,
            )
            if not isinstance(return_type, ir.VoidType) and not self._supports_runtime_type(
                return_type
            ):
                return False

            for parameter in symbol.signature.parameters:
                parameter_type = self._function_parameter_type(
                    parameter.type_spec,
                )
                if isinstance(parameter_type, ir.VoidType) or not self._supports_runtime_type(
                    parameter_type
                ):
                    return False
        except (AttributeError, TypeError, ValueError):
            return False

        if symbol.scope is None:
            return True

        try:
            chain_parameters = {
                parameter.name
                for parameter in symbol.signature.parameters
                if parameter.type_spec.name == 'chain'
            }
            variables = getattr(symbol, 'local_variables', None)
            if variables is None:
                variables = symbol.scope.namespace
            for variable in variables.values():
                if (
                    getattr(variable, 'name', None) in chain_parameters
                    and variable.type_spec.name == 'chain'
                ):
                    variable_type = ir.IntType(8).as_pointer()
                else:
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
        if isinstance(
            value_type_,
            (
                ir.IntType,
                ir.HalfType,
                ir.FloatType,
                ir.DoubleType,
                ir.PointerType,
            ),
        ):
            return True
        if isinstance(value_type_, ir.ArrayType):
            return FunctionEmitterBase._supports_runtime_type(value_type_.element)
        # Identified structs are legal storage for member access.  Keep this
        # name-based check compatible with llvmlite versions that expose the
        # literal/identified classes differently.
        return value_type_.__class__.__name__ in {
            'IdentifiedStructType',
            'LiteralStructType',
        }

    def _function_parameter_type(self, type_spec: TypeSpec) -> ir.Type:
        """Return the ABI type used for one function parameter.

        Arrays are references to their complete storage.  Unsized one-
        dimensional arrays already resolve to element pointers; fixed arrays
        need one pointer layer added around their complete LLVM array type.
        """
        parameter_type = llvm_type(
            type_spec,
            type_registry=self.type_registry,
        )
        if type_spec.array_depth and not isinstance(parameter_type, ir.PointerType):
            return parameter_type.as_pointer()
        return parameter_type

    def _function_type(self, symbol: FunctionSymbol) -> ir.FunctionType:
        try:
            parameters = [
                self._function_parameter_type(parameter.type_spec)
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
        current = self._unwrap(node)
        if getattr(current, 'name', None) == 'POSTFIX_EXPR':
            children = self._children(current)
            primary = children[0] if children else None
            base_name = self._identifier(primary)
            base_spec = self._active_specs.get(base_name or '')
            if base_spec is not None and self.type_registry is not None:
                suffixes: list[object] = []
                for child in children[1:]:
                    suffixes.extend(
                        self._children(child) if isinstance(child, list) else [child]
                    )
                for suffix in suffixes:
                    if getattr(suffix, 'name', None) != 'MEMBER_ACCESS':
                        continue
                    field = self.type_registry.field_spec(
                        base_spec.name,
                        self._identifier(suffix) or '',
                    )
                    field_spec = getattr(field, 'type_spec', None)
                    if field_spec is not None:
                        return field_spec.name in UNSIGNED_INTEGER_TYPES
        name = self._identifier(node)
        if name is None:
            return False
        spec = self._active_specs.get(name)
        return spec is not None and spec.name in UNSIGNED_INTEGER_TYPES

    @staticmethod
    def _condition_value(node: object) -> object | None:
        condition = next(
            (
                child for child in FunctionEmitterBase._children(node)
                if getattr(child, 'name', None) == 'CONDITION'
            ),
            None,
        )
        if condition is None:
            return None
        return next(
            (
                child for child in FunctionEmitterBase._children(condition)
                if getattr(child, 'name', None) == 'VALUE'
            ),
            None,
        )

    def _compile_condition(
        self,
        node: object,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
        *,
        require_bool: bool = False,
        condition_kind: str = 'control',
    ) -> ir.Value:
        value_node = self._condition_value(node)
        if value_node is None:
            raise FunctionEmissionError('La condicion no tiene una expresion')
        result = self._compile_expression(value_node, builder, values)
        if isinstance(result.type, ir.IntType):
            if result.type.width == 1:
                return result
            if require_bool:
                raise FunctionEmissionError(
                    f'La condicion de {condition_kind} debe producir bool'
                )
            return builder.icmp_unsigned(
                '!=',
                result,
                ir.Constant(result.type, 0),
            )
        if require_bool:
            raise FunctionEmissionError(
                f'La condicion de {condition_kind} debe producir bool'
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

    @staticmethod
    def _is_float_type(value_type_: ir.Type) -> bool:
        return isinstance(
            value_type_,
            (ir.HalfType, ir.FloatType, ir.DoubleType),
        )

    @staticmethod
    def _float_rank(value_type_: ir.Type) -> int:
        if isinstance(value_type_, ir.HalfType):
            return 16
        if isinstance(value_type_, ir.FloatType):
            return 32
        if isinstance(value_type_, ir.DoubleType):
            return 64
        raise FunctionEmissionError('Se esperaba un tipo flotante en LLVM')

    def _coerce_float(
        self,
        value: ir.Value,
        target_type: ir.Type,
        builder: ir.IRBuilder,
        signed: bool = True,
    ) -> ir.Value:
        if value.type == target_type:
            return value
        if self._is_float_type(value.type) and self._is_float_type(target_type):
            if self._float_rank(value.type) < self._float_rank(target_type):
                return builder.fpext(value, target_type)
            return builder.fptrunc(value, target_type)
        if isinstance(value.type, ir.IntType) and self._is_float_type(target_type):
            return (
                builder.sitofp(value, target_type)
                if signed
                else builder.uitofp(value, target_type)
            )
        raise FunctionEmissionError(
            f'No se puede convertir {value.type} a {target_type} en LLVM'
        )

    def _coerce_value(
        self,
        value: ir.Value,
        target_type: ir.Type,
        builder: ir.IRBuilder,
        signed: bool = True,
    ) -> ir.Value:
        if value.type == target_type:
            return value
        if self._is_float_type(target_type):
            return self._coerce_float(value, target_type, builder, signed)
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

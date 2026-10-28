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
            return FunctionEmitterBase._supports_runtime_type(value_type_.element)
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

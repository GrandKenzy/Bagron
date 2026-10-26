from __future__ import annotations

from typing import TYPE_CHECKING

from llvmlite import ir

from core.frontend.objects import FunctionSymbol

if TYPE_CHECKING:
    from core.storage import Storage


class FunctionEmissionError(ValueError):
    """Raised when a supported function cannot be represented in LLVM yet."""


class FunctionEmitter:
    """Emit the first executable entrypoint supported by the backend."""

    def __init__(self, module: ir.Module):
        self.module = module

    def emit_storage(self, storage: Storage) -> None:
        main = storage.functions.get('main')
        if main is not None:
            self.emit_main(main)

    def emit_main(self, symbol: FunctionSymbol) -> None:
        if symbol.signature.parameters:
            raise FunctionEmissionError(
                'El entrypoint main no puede tener parametros'
            )
        if symbol.signature.return_type.name != 'bool':
            raise FunctionEmissionError(
                'El entrypoint main debe retornar bool'
            )
        if len(symbol.return_values) != 1:
            raise FunctionEmissionError(
                'El entrypoint main requiere un unico return literal bool'
            )
        if not symbol.body_supported_for_entrypoint:
            raise FunctionEmissionError(
                'El entrypoint main solo admite por ahora un return literal bool'
            )

        value = symbol.return_values[0]
        if not value.is_literal or value.type_spec.name != 'bool':
            raise FunctionEmissionError(
                'El entrypoint main requiere un return literal bool'
            )

        bool_type = ir.IntType(1)
        source_type = ir.FunctionType(bool_type, [])
        source_function = ir.Function(
            self.module,
            source_type,
            name='__bagron_main',
        )
        source_function.linkage = 'internal'
        source_block = source_function.append_basic_block(name='entry')
        source_builder = ir.IRBuilder(source_block)
        source_builder.ret(ir.Constant(bool_type, bool(value.value)))

        native_type = ir.FunctionType(ir.IntType(32), [])
        native_function = ir.Function(self.module, native_type, name='main')
        native_block = native_function.append_basic_block(name='entry')
        native_builder = ir.IRBuilder(native_block)
        result = native_builder.call(source_function, [])
        exit_code = native_builder.select(
            result,
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), 1),
        )
        native_builder.ret(exit_code)


__all__ = ['FunctionEmissionError', 'FunctionEmitter']

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

        function_type = ir.FunctionType(ir.IntType(1), [])
        function = ir.Function(self.module, function_type, name='main')
        block = function.append_basic_block(name='entry')
        builder = ir.IRBuilder(block)
        builder.ret(ir.Constant(ir.IntType(1), bool(value.value)))


__all__ = ['FunctionEmissionError', 'FunctionEmitter']

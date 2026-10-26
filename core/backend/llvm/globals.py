from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from core.backend.llvm.types import LLVMTypeError, constant_value, zero_value
from core.frontend.objects import ValueInfo, Variable

if TYPE_CHECKING:
    from llvmlite import ir
    from core.storage import Storage


class GlobalEmissionError(ValueError):
    """Raised when a global cannot be represented as a static LLVM initializer."""


class GlobalEmitter:
    def __init__(self, module: ir.Module):
        self.module = module
        self._resolving: list[str] = []

    def emit_storage(self, storage: Storage) -> None:
        for symbol in storage.namespace.values():
            if isinstance(symbol, Variable):
                self.emit_symbol(storage, symbol)

    def _constant_value(self, storage: Storage, symbol: Variable) -> ValueInfo | None:
        if symbol.name in self._resolving:
            chain = ' -> '.join((*self._resolving, symbol.name))
            raise GlobalEmissionError(f'Ciclo de inicializacion global: {chain}')

        self._resolving.append(symbol.name)
        try:
            if not symbol.initialized:
                if symbol.value_is_const:
                    raise GlobalEmissionError(
                        f'El global const {symbol.name} no tiene inicializador'
                    )
                return None

            value = symbol.value_info
            if value is None:
                raise GlobalEmissionError(
                    f'No existe un valor semantico para el global {symbol.name}'
                )

            return self._resolve_value(storage, value)
        finally:
            self._resolving.pop()

    def _resolve_value(self, storage: Storage, value: ValueInfo) -> ValueInfo:
        if value.identifier is not None:
            target = storage.namespace.get(value.identifier)
            if not isinstance(target, Variable):
                raise GlobalEmissionError(
                    f'El inicializador no referencia un global: {value.identifier}'
                )
            if not target.value_is_const:
                raise GlobalEmissionError(
                    f'El global mutable {target.name} no puede usarse como inicializador estatico'
                )
            resolved = self._constant_value(storage, target)
            if resolved is None:
                raise GlobalEmissionError(
                    f'El global const {target.name} no tiene un valor estatico'
                )
            return resolved

        if not value.items:
            return value

        resolved_items = tuple(
            self._resolve_value(storage, item)
            for item in value.items
        )
        return replace(value, value=resolved_items, items=resolved_items)

    def emit_symbol(self, storage: Storage, symbol: Variable) -> None:
        if symbol.type_spec is None:
            raise GlobalEmissionError(f'El global {symbol.name} no tiene TypeSpec')

        if symbol.type_spec.name == 'callptr':
            raise GlobalEmissionError(
                f'callptr global aun no tiene emision LLVM: {symbol.name}'
            )

        try:
            value = self._constant_value(storage, symbol)
            initializer = (
                zero_value(symbol.type_spec, value)
                if value is None
                else constant_value(symbol.type_spec, value)
            )
        except LLVMTypeError as error:
            raise GlobalEmissionError(f'{symbol.name}: {error}') from error

        if symbol.name in self.module.globals:
            raise GlobalEmissionError(f'Simbolo LLVM duplicado: {symbol.name}')

        from llvmlite import ir

        global_value = ir.GlobalVariable(
            self.module,
            initializer.type,
            symbol.name,
        )

        global_value.initializer = initializer
        global_value.global_constant = symbol.value_is_const
        if symbol.privacy == 'private':
            global_value.linkage = 'internal'

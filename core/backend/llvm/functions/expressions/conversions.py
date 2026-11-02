from __future__ import annotations

from llvmlite import ir

from ..errors import FunctionEmissionError


class ConversionExpressionMixin:
    """Lower source-level conversions that need temporary LLVM storage."""

    def _chain_literal_value(self, argument: object) -> str | None:
        """Return the rodata text represented by a chain argument."""
        current = self._unwrap(argument)
        kind = self._token_kind(current)
        if kind == 'STRING':
            value = self._token_value(current)
            return value if isinstance(value, str) else None
        if kind != 'IDENT':
            return None

        name = str(self._token_value(current))
        info = self._active_values.get(name)
        if info is None:
            info = self._global_values.get(name)
        type_spec = self._active_type_spec(name)
        if type_spec is None:
            type_spec = getattr(info, 'type_spec', None)
        if (
            info is None
            or getattr(type_spec, 'name', None) != 'chain'
            or not getattr(info, 'is_literal', False)
            or getattr(getattr(info, 'type_spec', None), 'name', None) != 'chain'
        ):
            return None
        value = getattr(info, 'value', None)
        return value if isinstance(value, str) else None

    def _is_chain_array_argument(
        self,
        argument: object,
        target_spec: object,
    ) -> bool:
        """Identify a frontend-approved chain-to-``char[]`` argument."""
        return (
            getattr(target_spec, 'name', None) == 'char'
            and getattr(target_spec, 'pointer_level', 0) == 0
            and getattr(target_spec, 'array_depth', 0) == 1
            and self._chain_literal_value(argument) is not None
        )

    def _compile_chain_array_copy(
        self,
        argument: object,
        target_type: ir.Type,
        builder: ir.IRBuilder,
        values: dict[str, ir.Value],
    ) -> ir.Value:
        """Copy a constant chain into mutable call-local char storage."""
        text = self._chain_literal_value(argument)
        if text is None:
            raise FunctionEmissionError(
                'La conversion implicita a char[] requiere un chain constante'
            )
        try:
            data = text.encode('ascii')
        except UnicodeEncodeError as error:
            raise FunctionEmissionError(
                'Un chain usado como char[] solo puede contener ASCII'
            ) from error

        target_array = (
            target_type.pointee
            if isinstance(target_type, ir.PointerType)
            and isinstance(target_type.pointee, ir.ArrayType)
            else None
        )
        capacity = target_array.count if target_array is not None else len(data) + 1
        array_type = ir.ArrayType(ir.IntType(8), capacity)
        storage = builder.alloca(array_type, name='chain.char_array.tmp')
        storage.align = 1
        source = self._compile_expression(
            argument,
            builder,
            values,
            expected_type=ir.IntType(8).as_pointer(),
        )
        if not isinstance(source.type, ir.PointerType):
            raise FunctionEmissionError(
                'El chain no tiene una representacion de puntero en rodata'
            )

        zero = ir.Constant(ir.IntType(32), 0)
        for index in range(len(data)):
            offset = ir.Constant(ir.IntType(32), index)
            source_address = builder.gep(source, [offset], inbounds=True)
            byte = builder.load(source_address)
            target_address = builder.gep(
                storage,
                [zero, offset],
                inbounds=True,
            )
            builder.store(byte, target_address)

        terminator = builder.gep(
            storage,
            [zero, ir.Constant(ir.IntType(32), len(data))],
            inbounds=True,
        )
        builder.store(ir.Constant(ir.IntType(8), 0), terminator)

        if isinstance(target_type, ir.PointerType) and isinstance(
            target_type.pointee,
            ir.ArrayType,
        ):
            return storage
        pointer = builder.gep(storage, [zero, zero], inbounds=True)
        if pointer.type != target_type:
            raise FunctionEmissionError(
                'La copia chain -> char[] no coincide con el ABI del parametro'
            )
        return pointer


__all__ = ['ConversionExpressionMixin']

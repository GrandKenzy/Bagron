from __future__ import annotations

from llvmlite import ir


class StringPool:
    """Intern immutable chains and fixed character arrays in module rodata.

    String literals can be reached from global aggregate initializers and from
    function bodies.  Keeping the pool at module scope prevents those two
    emitters from creating duplicate storage for the same literal.
    """

    def __init__(self, module: ir.Module):
        self.module = module
        self._literals: dict[bytes, ir.GlobalVariable] = {}
        self._arrays: dict[tuple[bytes, int], ir.GlobalVariable] = {}

    def _constant_bytes(
        self,
        data: bytes | tuple[int, ...],
        *,
        name: str,
        storage_length: int | None = None,
    ) -> ir.GlobalVariable:
        length = len(data) if storage_length is None else storage_length
        if length < len(data):
            raise ValueError('El almacenamiento rodata es menor que sus datos')
        byte_type = ir.IntType(8)
        array_type = ir.ArrayType(byte_type, length)
        global_value = ir.GlobalVariable(
            self.module,
            array_type,
            name=name,
        )
        global_value.linkage = 'private'
        global_value.global_constant = True
        # These addresses are not observable through safe source operations.
        global_value.unnamed_addr = 'unnamed_addr'
        padded = (*data, *(0 for _ in range(length - len(data))))
        global_value.initializer = ir.Constant(
            array_type,
            [ir.Constant(byte_type, byte) for byte in padded],
        )
        return global_value

    def _global(self, value: str) -> ir.GlobalVariable:
        data = value.encode('utf-8')
        global_value = self._literals.get(data)
        if global_value is not None:
            return global_value

        global_value = self._constant_bytes(
            (*data, 0),
            name=f'__bagron_rodata_{len(self._literals) + len(self._arrays)}',
        )
        self._literals[data] = global_value
        return global_value

    def array_pointer(
        self,
        value: str,
        length: int,
    ) -> ir.Value:
        """Return a pointer to a fixed-size immutable ASCII char array."""
        data = value.encode('ascii')
        if length < len(data) + 1:
            raise ValueError('El array char no tiene espacio para NUL')
        key = (data, length)
        global_value = self._arrays.get(key)
        if global_value is None:
            global_value = self._constant_bytes(
                (*data, 0),
                name=f'__bagron_rodata_{len(self._literals) + len(self._arrays)}',
                storage_length=length,
            )
            self._arrays[key] = global_value
        return global_value

    def pointer(
        self,
        value: str,
        builder: ir.IRBuilder | None = None,
    ) -> ir.Value:
        """Return an ``i8*`` to the first byte of a NUL-terminated literal."""
        global_value = self._global(value)
        indices = [
            ir.Constant(ir.IntType(32), 0),
            ir.Constant(ir.IntType(32), 0),
        ]
        if builder is not None:
            return builder.gep(global_value, indices, inbounds=True)
        return global_value.gep(indices)

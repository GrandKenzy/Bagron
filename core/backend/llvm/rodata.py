from __future__ import annotations

from llvmlite import ir


class StringPool:
    """Emit one private, immutable rodata object for each byte sequence.

    String literals can be reached from global aggregate initializers and from
    function bodies.  Keeping the pool at module scope prevents those two
    emitters from creating duplicate storage for the same literal.
    """

    def __init__(self, module: ir.Module):
        self.module = module
        self._literals: dict[bytes, ir.GlobalVariable] = {}

    def _global(self, value: str) -> ir.GlobalVariable:
        data = value.encode('utf-8')
        global_value = self._literals.get(data)
        if global_value is not None:
            return global_value

        byte_type = ir.IntType(8)
        array_type = ir.ArrayType(byte_type, len(data) + 1)
        global_value = ir.GlobalVariable(
            self.module,
            array_type,
            name=f'__bagron_rodata_{len(self._literals)}',
        )
        global_value.linkage = 'private'
        global_value.global_constant = True
        # Chain addresses are not observable through the safe language API.
        # ``unnamed_addr`` lets LLVM merge identical immutable literals.
        global_value.unnamed_addr = 'unnamed_addr'
        global_value.initializer = ir.Constant(
            array_type,
            [ir.Constant(byte_type, byte) for byte in (*data, 0)],
        )
        self._literals[data] = global_value
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

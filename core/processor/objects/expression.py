from typing import Any
from core.processor.objects.base import Object

class BinaryExpr(Object):
    def __init__(self, left: Any, op: str, right: Any, in_scope: Object | None = None):
        super().__init__()
        self.left = left
        self.op = op
        self.right = right
        self.in_scope = in_scope
        self.compiled = ''

    @property
    def value(self) -> str:
        return f'{self.left} {self.op} {self.right}'

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __str__(self) -> str:
        return f'{self.left} {self.op} {self.right}'

    def __repr__(self) -> str:
        return f'BinaryExpr({self.left!r}, {self.op!r}, {self.right!r})'

class UnaryExpr(Object):
    def __init__(self, op: str, operand: Any, in_scope: Object | None = None):
        super().__init__()
        self.op = op
        self.operand = operand
        self.in_scope = in_scope
        self.compiled = ''

    @property
    def value(self) -> str:
        return f'{self.op}{self.operand}'

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __str__(self) -> str:
        return f'{self.op}{self.operand}'

    def __repr__(self) -> str:
        return f'UnaryExpr({self.op!r}, {self.operand!r})'

class LiteralExpr(Object):
    def __init__(self, value: Any, lit_type: str = 'any', in_scope: Object | None = None):
        super().__init__()
        self.value = value
        self.type = lit_type
        self.in_scope = in_scope
        self.compiled = ''

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __str__(self) -> str:
        if self.value is None or self.type == 'null':
            return 'NULL'
        if self.type == 'bool':
            return 'true' if self.value else 'false'
        if self.type == 'string':
            return f'"{self.value}"'
        return str(self.value)

    def __repr__(self) -> str:
        return f'LiteralExpr({self.value!r}, type={self.type!r})'

class VariableExpr(Object):
    def __init__(self, name: str, in_scope: Object | None = None):
        super().__init__()
        self.name = name
        self.in_scope = in_scope
        self.compiled = ''

    @property
    def value(self) -> str:
        return self.name

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __str__(self) -> str:
        return str(self.name)

    def __repr__(self) -> str:
        return f'VariableExpr({self.name!r})'

class IndexAccess(Object):
    __slots__ = (
        'target',
        'index',
        'indices',
        'scoped',
        'inferred_type',
    )

    def __init__(
        self,
        target: Any,
        index: Any = None,
        indices: list[Any] | None = None,
        in_scope: Object | None = None,
        scoped: Any = None,
        inferred_type: str | None = None,
    ):
        super().__init__()
        self.target = target
        if indices is not None:
            self.indices = list(indices)
        elif index is not None:
            self.indices = [index]
        else:
            self.indices = []
        self.index = index if index is not None else (self.indices[0] if self.indices else None)
        self.in_scope = in_scope
        self.scoped = scoped if scoped is not None else getattr(in_scope, 'function', None)
        self.inferred_type = inferred_type

    @property
    def value(self) -> str:
        idx_str = ''.join(f'[{i}]' for i in self.indices)
        return f'{self.target}{idx_str}'

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f'IndexAccess(target={self.target!r}, indices={self.indices!r})'

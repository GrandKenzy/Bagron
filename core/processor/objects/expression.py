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
    def __init__(self, target: Any, index: Any, in_scope: Object | None = None):
        super().__init__()
        self.target = target
        self.index = index
        self.in_scope = in_scope
        self.compiled = ''

    @property
    def value(self) -> str:
        return f'{self.target}[{self.index}]'

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __str__(self) -> str:
        return f'{self.target}[{self.index}]'

    def __repr__(self) -> str:
        return f'IndexAccess({self.target!r}, [{self.index!r}])'

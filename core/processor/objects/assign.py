from typing import Any
from core.processor.objects.base import Object

class Assign(Object):
    __slots__ = (
        'target',
        'op',
        'value',
        'scoped',
    )

    def __init__(
        self,
        target: Any,
        value: Any,
        op: str = '=',
        in_scope: Object | None = None,
        scoped: Any = None,
    ):
        super().__init__()
        self.target = target
        self.op = op
        self.value = value
        self.in_scope = in_scope
        self.scoped = scoped

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __repr__(self) -> str:
        return f'Assign(target={self.target!r}, op={self.op!r}, value={self.value!r})'

from typing import Any
from core.processor.objects.base import Object

class Assign(Object):
    def __init__(self, target: str, value: Any, in_scope: Object | None = None):
        super().__init__()
        self.target = target
        self.value = value
        self.in_scope = in_scope
        self.compiled: str = ''

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __repr__(self) -> str:
        return f'Assign(target={self.target}, value={self.value})'

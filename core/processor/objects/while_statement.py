from typing import Any
from core.processor.objects.base import Object

class WhileStatement(Object):
    def __init__(self, condition: Any, body: list[Object], in_scope: Object | None = None):
        super().__init__()
        self.condition = condition
        self.body = body
        self.in_scope = in_scope
        self.compiled: str = ''

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __repr__(self) -> str:
        return f'WhileStatement(condition={self.condition})'

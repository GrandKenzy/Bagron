from typing import Any
from core.processor.objects.base import Object

class ForStatement(Object):
    def __init__(self, var_name: str, mode: str, target: Any, body: list[Object], in_scope: Object | None = None):
        super().__init__()
        self.var_name = var_name
        self.mode = mode
        self.target = target
        self.body = body
        self.in_scope = in_scope
        self.compiled: str = ''

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __repr__(self) -> str:
        return f'ForStatement(var={self.var_name}, mode={self.mode}, target={self.target})'

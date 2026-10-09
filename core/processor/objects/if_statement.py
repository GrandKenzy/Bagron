from typing import Any
from core.processor.objects.base import Object

class IfStatement(Object):
    def __init__(self, condition: Any, body: list[Object], else_body: list[Object] | None = None, in_scope: Object | None = None):
        super().__init__()
        self.condition = condition
        self.body = body
        self.else_body = else_body or []
        self.in_scope = in_scope
        self.compiled: str = ''
        

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __repr__(self) -> str:
        return f'IfStatement(condition={self.condition}, body={self.body}, else_body={self.else_body})'

from typing import Any
from core.processor.objects.base import Object

class MethodCall(Object):
    def __init__(self, target: Any, method: str, args: list[Any], in_scope: Object | None = None):
        super().__init__()
        self.target = target
        self.method = method
        self.args = args
        self.in_scope = in_scope
        self.returntype: str = 'void'
        self.compiled: str = ''

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __repr__(self) -> str:
        return f'MethodCall(target={self.target}, method={self.method}, args={self.args})'

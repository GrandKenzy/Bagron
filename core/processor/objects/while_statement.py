from typing import Any
from core.processor.objects.base import Object, get_scope_function


class WhileStatement(Object):
    __slots__ = ('condition', 'body', 'in_scope', 'scoped')

    def __init__(self, condition: Any, body: list[Any], in_scope: Any = None, scoped: Any = None):
        super().__init__()
        self.condition = condition
        self.body = body
        self.in_scope = in_scope
        self.scoped = scoped if scoped is not None else get_scope_function(in_scope)

    def is_valid(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f'WhileStatement(condition={self.condition}, statements={len(self.body)})'


__all__ = [
    'WhileStatement',
]

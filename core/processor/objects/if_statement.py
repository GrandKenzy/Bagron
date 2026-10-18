from typing import Any
from core.processor.objects.base import Object, get_scope_function


class ElifClause(Object):
    __slots__ = ('condition', 'body')

    def __init__(self, condition: Any, body: list[Any]):
        super().__init__()
        self.condition = condition
        self.body = body

    def is_valid(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f'ElifClause(condition={self.condition}, statements={len(self.body)})'


class IfStatement(Object):
    __slots__ = ('condition', 'body', 'elifs', 'else_body', 'in_scope', 'scoped')

    def __init__(
        self,
        condition: Any,
        body: list[Any],
        elifs: list[ElifClause] | None = None,
        else_body: list[Any] | None = None,
        in_scope: Any = None,
        scoped: Any = None,
    ):
        super().__init__()
        self.condition = condition
        self.body = body
        self.elifs: list[ElifClause] = elifs if elifs is not None else []
        self.else_body: list[Any] = else_body if else_body is not None else []
        self.in_scope = in_scope
        self.scoped = scoped if scoped is not None else get_scope_function(in_scope)

    @property
    def elif_clauses(self) -> list[ElifClause]:
        return self.elifs

    def is_valid(self) -> bool:
        return True

    def __repr__(self) -> str:
        return (
            f'IfStatement(condition={self.condition}, '
            f'body={len(self.body)}, elifs={len(self.elifs)}, else={len(self.else_body)})'
        )


__all__ = [
    'ElifClause',
    'IfStatement',
]

from typing import Any
from core.processor.objects.base import Object, get_scope_function


class MemberAccess(Object):
    __slots__ = (
        'target',
        'member',
        'scoped',
        'inferred_type',
    )

    def __init__(
        self,
        target: Any,
        member: str,
        in_scope: Object | None = None,
        scoped: Any = None,
        inferred_type: str | None = None,
    ):
        super().__init__()
        self.target = target
        self.member = member
        self.in_scope = in_scope
        self.scoped = scoped if scoped is not None else get_scope_function(in_scope)
        self.inferred_type = inferred_type

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __repr__(self) -> str:
        return f'MemberAccess(target={self.target}, member={self.member})'


__all__ = ['MemberAccess']

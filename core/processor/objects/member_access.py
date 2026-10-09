from typing import Any
from core.processor.objects.base import Object

class MemberAccess(Object):
    def __init__(self, target: Any, member: str, in_scope: Object | None = None):
        super().__init__()
        self.target = target
        self.member = member
        self.in_scope = in_scope
        self.compiled: str = ''

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __repr__(self) -> str:
        return f'MemberAccess(target={self.target}, member={self.member})'

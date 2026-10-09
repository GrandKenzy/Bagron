from typing import Any
from core.processor.objects.base import Object

class Call(Object):
    def __init__(self, name: str, args: list[Any], kwargs: dict[str, Any] | None = None, in_scope: Object | None = None):
        super().__init__()
        self.name = name
        self.args = args
        self.kwargs = kwargs or {}
        self.in_scope = in_scope
        self.returntype: str = 'void'
        self.is_pointer: bool = False
        self.target_type: str | None = None
        self.compiled: str = ''

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __repr__(self) -> str:
        kw_str = f', kwargs={self.kwargs}' if self.kwargs else ''
        return f'Call(name={self.name}, args={self.args}{kw_str})'

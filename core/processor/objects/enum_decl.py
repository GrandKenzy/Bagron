from typing import Any, Literal
from core.processor.objects.base import Object

class EnumDecl(Object):
    def __init__(
        self,
        name: str,
        items: list[tuple[str, Any]] | None = None,
        privacity: Literal['public', 'private'] = 'public'
    ):
        self.name = name
        self.items = items or []
        self.members: dict[str, Any] = {k: v for k, v in self.items}
        self.privacity = privacity
        super().__init__()

    def is_valid(self):
        return False

    def __repr__(self) -> str:
        return f'EnumDecl(name={self.name}, items={self.items})'

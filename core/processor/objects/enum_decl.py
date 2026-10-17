from typing import Any, Literal
from core.processor.objects.base import Object


class EnumDecl(Object):
    __slots__ = ('name', 'c_name', 'items', 'members', 'privacy')

    def __init__(
        self,
        name: str,
        items: list[tuple[str, Any]] | None = None,
        privacy: Literal['public', 'private'] = 'public',
        c_name: str | None = None,
    ):
        super().__init__()
        self.name = name
        self.c_name: str = c_name if c_name is not None else name
        self.items = items or []
        self.members: dict[str, Any] = {k: v for k, v in self.items}
        self.privacy = privacy

    def is_valid(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"EnumDecl(name={self.name!r}, members={self.members}, privacy={self.privacy!r})"

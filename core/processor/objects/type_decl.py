from typing import Any, Literal
from core.processor.objects.base import Object

class TypeDecl(Object):
    def __init__(
        self,
        name: str,
        slots: list[dict] | None = None,
        kind: str | None = None,
        items: list[Any] | None = None,
        dtype: Any = None,
        accessors: dict[str, Any] | None = None,
        methods: dict[str, Any] | None = None,
        privacity: Literal['public', 'private'] = 'public'
    ):
        self.name = name
        self.slots = slots or []
        self.kind = kind
        self.items = items or []
        self.dtype = dtype
        self.accessors = accessors or {}
        self.methods = methods or {}
        self.privacity = privacity
        super().__init__()

    def is_valid(self):
        return False

    def __repr__(self) -> str:
        return f'TypeDecl(name={self.name}, kind={self.kind}, slots={self.slots}, dtype={self.dtype})'

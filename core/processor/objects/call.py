from typing import Any
from core.processor.objects.base import Object


class Call(Object):
    __slots__ = (
        'name',
        'args',
        'kwargs',
        'returntype',
        'is_pointer',
        'target_type',
        'scoped',
    )

    def __init__(
        self,
        name: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        in_scope: Object | None = None,
        scoped: Any = None,
    ):
        super().__init__()
        self.name = name
        self.args = args if args is not None else []
        self.kwargs = kwargs or {}
        self.in_scope = in_scope
        self.returntype: str = 'void'
        self.is_pointer: bool = False
        self.target_type: str | None = None
        from core.processor.objects.function import LocalStorage
        self.scoped = scoped if scoped is not None else (in_scope.function if isinstance(in_scope, LocalStorage) else None)

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

    def __repr__(self) -> str:
        kw_str = f', kwargs={self.kwargs}' if self.kwargs else ''
        return f'Call(name={self.name}, args={self.args}{kw_str})'


__all__ = ['Call']

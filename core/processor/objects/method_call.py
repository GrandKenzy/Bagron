from typing import Any
from core.processor.objects.base import Object


class MethodCall(Object):
    __slots__ = (
        'target',
        'method',
        'args',
        'kwargs',
        'returntype',
        'scoped',
    )

    def __init__(
        self,
        target: Any,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        in_scope: Object | None = None,
        scoped: Any = None,
    ):
        super().__init__()
        self.target = target
        self.method = method
        self.args = args if args is not None else []
        self.kwargs = kwargs or {}
        self.in_scope = in_scope
        from core.processor.objects.function import LocalStorage
        self.scoped = scoped if scoped is not None else (in_scope.function if isinstance(in_scope, LocalStorage) else None)

    def is_valid(self) -> bool:
        return not bool(self.in_scope)

class SuperInitCall(MethodCall):
    __slots__ = (
        'base_class',
    )

    def __init__(
        self,
        base_class: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        in_scope: Object | None = None,
        scoped: Any = None,
    ):
        super().__init__(
            target='super',
            method='__init__',
            args=args,
            kwargs=kwargs,
            in_scope=in_scope,
            scoped=scoped,
        )
        self.base_class = base_class
        self.returntype = 'void'

    def __repr__(self) -> str:
        kw_str = f', kwargs={self.kwargs}' if self.kwargs else ''
        return f'SuperInitCall(base_class={self.base_class}, args={self.args}{kw_str})'


__all__ = ['MethodCall', 'SuperInitCall']


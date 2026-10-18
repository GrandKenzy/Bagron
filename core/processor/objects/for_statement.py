from typing import Any
from core.processor.objects.base import Object, get_scope_function


class ForStatement(Object):
    __slots__ = ('targets', 'mode', 'iterable', 'body', 'in_scope', 'scoped')

    def __init__(
        self,
        targets: list[str] | str,
        mode: str,
        iterable: Any,
        body: list[Any],
        in_scope: Any = None,
        scoped: Any = None,
    ):
        super().__init__()
        self.targets = targets if isinstance(targets, list) else [targets]
        self.mode = mode
        self.iterable = iterable
        self.body = body
        self.in_scope = in_scope
        self.scoped = scoped if scoped is not None else get_scope_function(in_scope)

    @property
    def var_name(self) -> str:
        return self.targets[0] if self.targets else ''

    @property
    def target(self) -> Any:
        return self.iterable

    def is_valid(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f'ForStatement(targets={self.targets}, mode={self.mode}, statements={len(self.body)})'


__all__ = [
    'ForStatement',
]

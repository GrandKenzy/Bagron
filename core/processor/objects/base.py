from typing import Any, Optional


class Object:
    __slots__ = ('compiled', 'in_scope', 'uses')

    def __init__(self) -> None:
        ITEMS[self] = self.__class__.__name__
        self.compiled = ''
        self.in_scope: Optional['Object'] = None
        self.uses: int = 0

    def is_valid(self) -> bool:
        return False

    def ignore(self):
        ITEMS.pop(self, None)
        return self


ITEMS: dict[Object, str] = {}


def get_scope_function(in_scope: Any) -> Any:
    """Retorna la función asociada al scope si es un LocalStorage, o None."""
    from core.processor.objects.function import LocalStorage
    return in_scope.function if isinstance(in_scope, LocalStorage) else None


__all__ = ['Object', 'ITEMS', 'get_scope_function']

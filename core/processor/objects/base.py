from typing import Optional


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

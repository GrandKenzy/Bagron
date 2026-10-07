

class Object:
    def __init__(self) -> None:
        ITEMS[self] = self.__class__.__name__


ITEMS: dict[Object, str] = {}

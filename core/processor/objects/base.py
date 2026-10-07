

class Object:
    def __init__(self) -> None:
        ITEMS[self] = self.__class__.__name__

    def ignore(self):
        ITEMS.pop(self, None)
        
ITEMS: dict[Object, str] = {}

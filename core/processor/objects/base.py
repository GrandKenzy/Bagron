

class Object:
    def __init__(self) -> None:
        ITEMS[self] = self.__class__.__name__
        self.compiled = ''
        self.in_scope: Object |  None = None
        self.uses: int = 0
        
    def is_valid(self):
        return bool()
    
    def ignore(self):
        ITEMS.pop(self, None)
        return self
ITEMS: dict[Object, str] = {}

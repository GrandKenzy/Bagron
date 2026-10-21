from core.processor.objects.base import Object
from typing import Any
import gram
class Returned(Object):
    def __init__(self, value: Any) -> None:
        self.value = value
        super().__init__()
        
    def __repr__(self) -> str:
        return f"Return({self.value}, t={type(self.value)})"
    
    def is_identifier(self):
        return isinstance(self.value, gram.Identifier)
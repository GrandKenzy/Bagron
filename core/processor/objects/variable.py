from typing import Any, Literal

from core.processor.objects.base import Object

class Variable(Object):
    def __init__(self, name: str, value: Any, type: str, privacity: Literal['public', 'private'] = 'public', is_constant: bool = False):
        self.name = name
        self.value = value
        self.type = type
        self.privacity = privacity
        self.is_constant = is_constant
        super().__init__()
        
    def __repr__(self) -> str:
        return f'Variable(name={self.name}, value={self.type}, type={self.type}, const={self.is_constant}, privacity={self.privacity})'
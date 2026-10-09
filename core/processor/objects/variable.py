from typing import Any, Literal

from core.processor.objects.base import Object

class Variable(Object):
    def __init__(self, name: str, value: Any, type: str, privacity: Literal['public', 'private'] = 'public', is_constant: bool = False):
        self.name = name
        self.value = value
        self.type = type
        self.privacity = privacity
        self.is_constant = is_constant
        self.ref: bool = False
        self.is_pointer: bool = False
        self.pointer_base_type: str | None = None
        self.fixed_size: int | None = None
        self.compiled = ''

        super().__init__()
        
    def is_valid(self):
        if self.type == 'type':
            return False
        if self.in_scope:
            if self.uses == 0:
                return False 
        else:
            if self.privacity == 'private' and self.uses == 0:
                return False
        return True
        
    def __repr__(self) -> str:
        return f'Variable(name={self.name}, value={self.type}, type={self.type}, const={self.is_constant}, privacity={self.privacity})'
    

from typing import Any, Literal
from core.processor.objects.variable import Variable
from core.processor.objects.base import Object
from core.processor.objects.returned import Returned

class Function(Object):
    def __init__(self, name: str, body: dict[Object, str], retur_type: str, parameters: list[tuple[str, str]], privacity: Literal['public', 'private'] = 'public'):
        self.name = name
        self.return_type = retur_type
        self.returned: Returned | None = None
        self.parameters = parameters
        self.body = body
        self.privacity = privacity
        self.compiled = ""
        super().__init__()
        
    def is_valid(self):
        return True
        
    def get_vars(self):
        vars = []
        for item in self.body.keys():
            if isinstance(item, Variable):
                vars.append(item)
        return vars
    
    def rescope(self):
        for b in self.body.keys():
            b.in_scope = self
            
        return self
    
    def __repr__(self) -> str:
        return f'Function(name={self.name}, returned={self.returned}, parameters={self.parameters}, privacity={self.privacity})'
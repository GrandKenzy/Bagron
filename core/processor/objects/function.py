from typing import Any, Literal
from core.processor.objects.variable import Variable
from core.processor.objects.base import Object
from core.processor.objects.returned import Returned

class FunctionParam:
    def __init__(self, param_type: str, name: str, is_variadic: bool = False, default: Any = None, has_default: bool = False):
        self.type = param_type
        self.name = name
        self.is_variadic = is_variadic
        self.default = default
        self.has_default = has_default

    def __iter__(self):
        return iter((self.type, self.name))

    def __getitem__(self, idx):
        return (self.type, self.name)[idx]

    def __len__(self):
        return 2

    def __repr__(self) -> str:
        star = '*' if self.is_variadic else ''
        def_str = f'={self.default!r}' if self.has_default else ''
        return f'{self.type} {star}{self.name}{def_str}'

class Function(Object):
    def __init__(self, name: str, body: dict[Object, str], retur_type: str, parameters: list[Any], privacity: Literal['public', 'private'] = 'public'):
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
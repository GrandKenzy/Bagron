from typing import Any, Literal

from core.processor.objects.base import Object

class Function(Object):
    def __init__(self, name: str, body: list, returned: str, parameters: list[tuple[str, str]], privacity: Literal['public', 'private'] = 'public'):
        self.name = name
        self.returned = returned
        self.parameters = parameters
        self.body = body
        self.privacity = privacity
        super().__init__()
        
    def __repr__(self) -> str:
        return f'Function(name={self.name}, returned={self.returned}, parameters={self.parameters}, privacity={self.privacity})'
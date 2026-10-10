from typing import Any, Literal
from core.processor.objects.base import Object

class ClassMethod:
    def __init__(
        self,
        name: str,
        return_type: str = 'void',
        params: list[Any] | None = None,
        decorator: str | None = None,
        body_node: Any = None,
        privacity: Literal['public', 'private'] = 'public'
    ):
        self.name = name
        self.return_type = return_type
        self.params = params or []
        self.decorator = decorator
        self.body_node = body_node
        self.privacity = privacity
        self.is_magic = name.startswith('__') and name.endswith('__')

    def __repr__(self) -> str:
        return f'ClassMethod(name={self.name}, ret={self.return_type}, decorator={self.decorator})'

class ClassDecl(Object):
    def __init__(
        self,
        name: str,
        methods: dict[str, ClassMethod] | None = None,
        fields: list[Any] | None = None,
        privacity: Literal['public', 'private'] = 'public'
    ):
        self.name = name
        self.methods = methods or {}
        self.fields = fields or []
        self.privacity = privacity
        self.constructor_func: Any = None
        self.generated_functions: list[Any] = []
        super().__init__()

    def is_valid(self):
        return False

    def __repr__(self) -> str:
        return f'ClassDecl(name={self.name}, methods={list(self.methods.keys())})'

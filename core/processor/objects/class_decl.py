from typing import Any, Literal
from core.processor.objects.base import Object, get_scope_function


class ClassField:
    __slots__ = ('name', 'type', 'value', 'is_static', 'privacy', 'fixed_size')

    def __init__(
        self,
        name: str,
        type: str,
        value: Any = None,
        is_static: bool = False,
        privacy: str = 'public',
        fixed_size: int | None = None,
    ):
        self.name = name
        self.type = type
        self.value = value
        self.is_static = is_static
        self.privacy = privacy
        self.fixed_size = fixed_size

    def __repr__(self) -> str:
        static_str = "static " if self.is_static else ""
        val_str = f" = {self.value}" if self.value is not None else ""
        return f"{static_str}{self.type} {self.name}{val_str}"


class ClassMethod(Object):
    __slots__ = (
        'name',
        'return_type',
        'parameters',
        'kind',
        'decorator',
        'body',
        'scope',
        'class_decl',
        'privacy',
        'is_magic',
        'scoped',
        'has_super_init',
    )

    def __init__(
        self,
        name: str,
        return_type: str = 'void',
        parameters: list[Any] | None = None,
        kind: Literal['instance', 'classmethod', 'staticmethod'] = 'instance',
        decorator: str | None = None,
        body: Any = None,
        scope: Any = None,
        class_decl: Any = None,
        privacy: Literal['public', 'private'] = 'public',
        in_scope: Object | None = None,
        scoped: Any = None,
    ):
        super().__init__()
        self.name = name
        self.return_type = return_type
        self.parameters = parameters if parameters is not None else []
        self.kind = kind
        self.decorator = decorator
        self.body = body if body is not None else []
        self.scope = scope
        self.class_decl = class_decl
        self.privacy = privacy
        self.is_magic = name.startswith('__') and name.endswith('__')
        self.in_scope = in_scope
        self.scoped = scoped if scoped is not None else get_scope_function(in_scope)
        self.has_super_init: bool = False

    @property
    def params(self) -> list[Any]:
        return self.parameters

    def is_valid(self) -> bool:
        return True

    def __repr__(self) -> str:
        dec_str = f"@{self.decorator} " if self.decorator else ""
        return f"ClassMethod({dec_str}{self.return_type} {self.name}, kind={self.kind!r})"


class ClassDecl(Object):
    __slots__ = (
        'name',
        'privacy',
        'bases',
        'class_fields',
        'instance_fields',
        'methods',
        'class_methods',
        'static_methods',
        'instance_methods',
        'init_method',
        'new_method',
        'scoped',
    )

    def __init__(
        self,
        name: str,
        privacy: Literal['public', 'private'] = 'public',
        bases: list[str] | None = None,
        class_fields: dict[str, ClassField] | None = None,
        instance_fields: dict[str, ClassField] | None = None,
        methods: dict[str, ClassMethod] | None = None,
        class_methods: dict[str, ClassMethod] | None = None,
        static_methods: dict[str, ClassMethod] | None = None,
        instance_methods: dict[str, ClassMethod] | None = None,
        init_method: ClassMethod | None = None,
        new_method: ClassMethod | None = None,
        in_scope: Object | None = None,
        scoped: Any = None,
    ):
        super().__init__()
        self.name = name
        self.privacy = privacy
        self.bases = bases or []
        self.class_fields = class_fields or {}
        self.instance_fields = instance_fields or {}
        self.methods = methods or {}
        self.class_methods = class_methods or {}
        self.static_methods = static_methods or {}
        self.instance_methods = instance_methods or {}
        self.init_method = init_method
        self.new_method = new_method
        self.in_scope = in_scope
        self.scoped = scoped if scoped is not None else get_scope_function(in_scope)

    @property
    def fields(self) -> dict[str, ClassField]:
        return {**self.class_fields, **self.instance_fields}

    def is_valid(self) -> bool:
        return True

    def __repr__(self) -> str:
        return (
            f"ClassDecl(name={self.name!r}, bases={self.bases}, "
            f"methods={list(self.methods.keys())}, "
            f"class_fields={list(self.class_fields.keys())}, "
            f"instance_fields={list(self.instance_fields.keys())})"
        )


__all__ = [
    'ClassField',
    'ClassMethod',
    'ClassDecl',
]

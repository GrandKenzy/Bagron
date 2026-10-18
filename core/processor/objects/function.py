from typing import Any, Literal
from core.processor.objects.array import Array
from core.processor.objects.base import Object
from core.processor.objects.returned import Returned
from core.processor.objects.variable import Variable



class FunctionParam:
    __slots__ = ('type', 'name', 'is_variadic', 'default', 'has_default', 'value', 'uses')

    def __init__(
        self,
        param_type: str,
        name: str,
        is_variadic: bool = False,
        default: Any = None,
        has_default: bool = False,
    ):
        self.type = param_type
        self.name = name
        self.is_variadic = is_variadic
        self.default = default
        self.has_default = has_default
        self.value = default
        self.uses = 0

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


class LocalStorage:
    __slots__ = ('function', 'parent', 'variables', 'parameters')

    def __init__(self, function: 'Function', parent: Any):
        self.function = function
        self.parent = parent
        self.variables: dict[str, Variable] = {}
        self.parameters: dict[str, FunctionParam] = {}

    def collition_name(self, name: str, raise_error: bool = True) -> bool:
        from core.initiator.reserve_funnames import MagicFuncsManager

        if MagicFuncsManager.exists(name):
            if raise_error:
                raise RuntimeError(
                    f"Colisión en función '{self.function.name}': el símbolo '{name}' es una función intrínseca reservada y no puede ser reemplazado."
                )
            return True

        collided = name in self.parameters or name in self.variables
        if collided and raise_error:
            raise RuntimeError(
                f"Colisión en función '{self.function.name}': el símbolo local '{name}' ya existe."
            )
        return collided

    def resolve(self, name: str) -> Any | None:
        if name in self.variables:
            return self.variables[name]
        if name in self.parameters:
            return self.parameters[name]
        if self.parent is not None:
            return self.parent.resolve(name)
        return None

    def resolve_type(self, type_name: str) -> str:
        if self.parent is not None:
            return self.parent.resolve_type(type_name)
        return type_name

    def find_struct(self, name: str, visited: set[int] | None = None) -> Any | None:
        if self.parent is not None:
            return self.parent.find_struct(name, visited)
        return None

    def find_enum(self, name: str, visited: set[int] | None = None) -> Any | None:
        if self.parent is not None:
            return self.parent.find_enum(name, visited)
        return None

    def find_function(self, name: str, visited: set[int] | None = None) -> Any | None:
        if self.parent is not None:
            return self.parent.find_function(name, visited)
        return None

    @property
    def structs(self) -> dict:
        return self.parent.structs if self.parent is not None else {}

    @property
    def enums(self) -> dict:
        return self.parent.enums if self.parent is not None else {}

    @property
    def types(self) -> dict:
        return self.parent.types if self.parent is not None else {}

    @property
    def declarations(self) -> dict:
        return self.parent.declarations if self.parent is not None else {}

    @property
    def modules(self) -> dict:
        return self.parent.modules if self.parent is not None else {}

    @property
    def molds(self) -> dict:
        return self.parent.molds if self.parent is not None else {}

    @property
    def flags(self) -> dict:
        return self.parent.flags if self.parent is not None else {}

    @property
    def classes(self) -> dict:
        return self.parent.classes if self.parent is not None else {}

    def add_variable(
        self,
        name: str,
        var_type: str,
        value: Any = None,
        privacy: str = 'public',
        is_constant: bool = False,
        fixed_size: int | None = None,
        pointer_base_type: str | None = None,
        is_cptr: bool = False,
        is_ptr: bool = False,
        array: Array | None = None,
    ) -> Variable:
        computed_is_cptr = is_cptr or var_type == 'cptr'
        computed_is_ptr = is_ptr or var_type == 'ptr'
        actual_type = 'void' if var_type in ('cptr', 'ptr') else var_type

        if array is None and (fixed_size is not None or var_type.startswith('array[')):
            elem_type = var_type[6:-1].split(',')[0].strip() if var_type.startswith('array[') else var_type
            if elem_type in ('cptr', 'ptr'):
                elem_type = 'void'
            array = Array(
                element_type=elem_type,
                size=fixed_size,
                is_cptr=computed_is_cptr,
                is_ptr=computed_is_ptr,
                pointer_base_type=pointer_base_type or (elem_type if (computed_is_cptr or computed_is_ptr) else None),
            )

        pointer_base_t = pointer_base_type or (actual_type if (computed_is_cptr or computed_is_ptr) else None)
        var_obj = Variable(
            name=name,
            value=value,
            type=actual_type,
            privacy=privacy,  # type: ignore
            is_constant=is_constant or name.isupper() or computed_is_cptr,
            is_cptr=computed_is_cptr,
            is_ptr=computed_is_ptr,
            array=array,
            pointer_base_type=pointer_base_t,
        )
        if fixed_size is not None:
            var_obj.fixed_size = fixed_size
        self.variables[name] = var_obj
        return var_obj



    @property
    def privacy(self) -> str:
        return self.parent.privacy if self.parent is not None else 'public'


class Function(Object):
    __slots__ = (
        'name',
        'return_type',
        'returned',
        'parameters',
        'body',
        'privacy',
        'is_inline',
        'inline_target',
        'decorators',
        'scope',
        'c_name',
    )

    def __init__(
        self,
        name: str,
        return_type: str,
        parameters: list[Any] | Any = None,
        body: Any = None,
        privacy: Literal['public', 'private'] | str = 'public',
        is_inline: bool = False,
        inline_target: Any = None,
        decorators: list[Any] | None = None,
        scope: LocalStorage | None = None,
        c_name: str | None = None,
    ):
        super().__init__()
        self.name = name
        self.return_type = return_type
        self.returned: Returned | None = None
        self.parameters = parameters if parameters is not None else []
        self.body = body if body is not None else []
        self.privacy = privacy
        self.is_inline = is_inline
        self.inline_target = inline_target
        self.decorators = decorators if decorators is not None else []
        self.scope = scope
        self.c_name = c_name or name

    def is_valid(self):
        return bool(self.name)

    def get_vars(self):
        vars = []
        if self.scope is not None:
            return list(self.scope.variables.values())
        if isinstance(self.body, dict):
            for item in self.body.keys():
                if isinstance(item, Variable):
                    vars.append(item)
        elif isinstance(self.body, list):
            for item in self.body:
                if isinstance(item, Variable):
                    vars.append(item)
        return vars

    def rescope(self):
        if isinstance(self.body, dict):
            for b in self.body.keys():
                if isinstance(b, Object):
                    b.in_scope = self
        elif isinstance(self.body, list):
            for b in self.body:
                if isinstance(b, Object):
                    b.in_scope = self
        return self

    def __repr__(self) -> str:
        return (
            f'Function(name={self.name}, return_type={self.return_type}, '
            f'privacy={self.privacy}, is_inline={self.is_inline})'
        )


__all__ = [
    'FunctionParam',
    'LocalStorage',
    'Function',
]
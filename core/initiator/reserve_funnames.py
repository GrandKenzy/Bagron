from typing import Any

DEFAULTS = [
    'print',
    'input',
    'EGL_Version',
    'malloc',
    'free',
    '__size__',
]

class ReservedParam:
    def __init__(self, name: str, param_type: str, is_variadic: bool = False, default: Any = None, has_default: bool = False):
        self.name = name
        self.type = param_type
        self.is_variadic = is_variadic
        self.default = default
        self.has_default = has_default

    def __repr__(self) -> str:
        star = '*' if self.is_variadic else ''
        def_str = f'={self.default!r}' if self.has_default else ''
        return f'{self.type} {star}{self.name}{def_str}'

class ReservedFuncName:
    _ITEMS_: dict[str, 'ReservedFuncName'] = {}

    def __init__(self, name: str, argtypes: list | dict | str, returntype: str):
        self.is_available(name)
        self.name = name
        self.returntype = returntype
        self.params: list[ReservedParam] = []
        self._parse_args(argtypes)
        self.param_map = {p.name: p for p in self.params}
        self.argnames = [p.name for p in self.params]
        self.argtypes = [p.type for p in self.params]
        self.variadic_param = next((p for p in self.params if p.is_variadic), None)
        ReservedFuncName._ITEMS_[name] = self

    def _parse_args(self, argtypes: list | dict | str):
        if isinstance(argtypes, dict):
            for k, v in argtypes.items():
                is_var = k.startswith('*')
                clean_name = k.lstrip('*')
                if isinstance(v, (tuple, list)) and len(v) == 2:
                    self.params.append(ReservedParam(clean_name, v[0], is_var, v[1], True))
                elif isinstance(v, ReservedParam):
                    self.params.append(v)
                else:
                    self.params.append(ReservedParam(clean_name, str(v), is_var))
        elif isinstance(argtypes, (list, tuple)):
            for idx, item in enumerate(argtypes):
                if item == 'void':
                    continue
                if item == 'all':
                    self.params.append(ReservedParam('values', 'all', True))
                elif isinstance(item, ReservedParam):
                    self.params.append(item)
                else:
                    self.params.append(ReservedParam(f'arg{idx}', str(item)))
        elif isinstance(argtypes, str):
            if argtypes != 'void':
                if argtypes == 'all':
                    self.params.append(ReservedParam('values', 'all', True))
                else:
                    self.params.append(ReservedParam('arg0', argtypes))

    def is_available(self, name: str):
        if name in ReservedFuncName._ITEMS_:
            print(f'Warning: func name {name} already exists')

    def bind_args(self, call_args: list, call_kwargs: dict | None = None) -> dict[str, Any]:
        call_kwargs = dict(call_kwargs or {})
        result: dict[str, Any] = {}
        pos_params: list[ReservedParam] = []
        var_param: ReservedParam | None = None
        post_var_params: list[ReservedParam] = []

        for p in self.params:
            if p.is_variadic:
                var_param = p
            elif var_param is None:
                pos_params.append(p)
            else:
                post_var_params.append(p)

        idx = 0
        for p in pos_params:
            if idx < len(call_args):
                result[p.name] = call_args[idx]
                idx += 1
            elif p.name in call_kwargs:
                result[p.name] = call_kwargs.pop(p.name)
            elif p.has_default:
                result[p.name] = p.default
            else:
                result[p.name] = None

        if var_param:
            remaining = list(call_args[idx:])
            result[var_param.name] = remaining
            idx = len(call_args)
        elif idx < len(call_args):
            result['_extra_args'] = list(call_args[idx:])

        for p in post_var_params:
            if p.name in call_kwargs:
                result[p.name] = call_kwargs.pop(p.name)
            elif p.has_default:
                result[p.name] = p.default
            else:
                result[p.name] = None

        for k, v in call_kwargs.items():
            result[k] = v

        return result

def get_items():
    return ReservedFuncName._ITEMS_

def exists(resname: str):
    return resname in ReservedFuncName._ITEMS_

r_print = ReservedFuncName('print', {'*values': 'type', 'sep': ('str', ' ')}, 'void')
r_input = ReservedFuncName('input', {'content': ('str', '')}, 'str')
r_version = ReservedFuncName('EGL_Version', {}, 'str')
r_malloc = ReservedFuncName('malloc', {'Type': 'type', 'size': ('int', 1)}, 'ptr')
r_free = ReservedFuncName('free', {'ptr': 'ptr'}, 'void')
r_size = ReservedFuncName('__size__', {'type': 'type'}, 'int')
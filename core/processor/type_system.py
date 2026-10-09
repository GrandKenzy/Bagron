from typing import Any

INTRINSIC_TYPES: dict[str, str] = {
    '__int_t__': 'int',
    '__int8_t__': 'int8_t',
    '__int16_t__': 'int16_t',
    '__int32_t__': 'int32_t',
    '__int64_t__': 'int64_t',
    '__uint_t__': 'unsigned int',
    '__uint8_t__': 'uint8_t',
    '__uint16_t__': 'uint16_t',
    '__uint32_t__': 'uint32_t',
    '__uint64_t__': 'uint64_t',
    '__float_t__': 'float',
    '__middle_t__': '_Float16',
    '__double_t__': 'double',
    '__char_t__': 'char',
    '__str_t__': 'char*',
    '__bool_t__': 'bool',
    '__ptr_t__': 'void*',
    '__void_t__': 'void',
    '__type_t__': '',
    '__arrof__': '',
    '__void_p_t__': 'void*',
    '__size_t__': 'size_t',
}

CUSTOM_TYPES: dict[str, dict[str, Any]] = {}

def register_type(
    name: str,
    intrinsic: str,
    field_name: str = 'value',
    slots: list[dict] | None = None,
    inner_args: list[str] | None = None
) -> dict[str, Any]:
    import gram
    name_str = str(name.value if hasattr(name, 'value') else name).strip()
    intrinsic_str = str(intrinsic.value if hasattr(intrinsic, 'value') else intrinsic).strip()
    field_str = str(field_name.value if hasattr(field_name, 'value') else field_name).strip()
    if intrinsic_str == '__void_p_t__' and inner_args:
        base_c = resolve_c_type(inner_args[0])
        c_type = f'{base_c}*'
    else:
        c_type = INTRINSIC_TYPES.get(intrinsic_str, intrinsic_str)
    entry = {
        'name': name_str,
        'intrinsic': intrinsic_str,
        'c_type': c_type,
        'field_name': field_str,
        'slots': slots or [],
        'inner_args': inner_args or [],
    }
    CUSTOM_TYPES[name_str] = entry
    if not gram.words.group_exists('types'):
        gram.words.add_group('types')
    gram.words.add_keyword(name_str, group='types', allow_override=True)
    return entry

def resolve_generic_type(type_name: str, type_args: list[Any]) -> tuple[str | None, int | None]:
    t_str = str(type_name.value if hasattr(type_name, 'value') else type_name).strip()
    entry = CUSTOM_TYPES.get(t_str)
    if not entry or entry.get('intrinsic') != '__arrof__':
        return None, None
    slots = entry.get('slots', [])
    inner_args = entry.get('inner_args', [])
    slot_map: dict[str, Any] = {}
    for i, slot in enumerate(slots):
        s_name = slot.get('name')
        if s_name and i < len(type_args):
            slot_map[s_name] = type_args[i]
    resolved_args = []
    for arg in inner_args:
        arg_str = str(arg.value if hasattr(arg, 'value') else arg).strip()
        if arg_str in slot_map:
            resolved_args.append(slot_map[arg_str])
        else:
            resolved_args.append(arg_str)
    elem_type = None
    fixed_size = None
    if len(resolved_args) >= 2:
        elem_type = str(resolved_args[0])
        try:
            fixed_size = int(resolved_args[1])
        except (ValueError, TypeError):
            fixed_size = None
    elif len(resolved_args) == 1:
        if str(resolved_args[0]).isdigit():
            fixed_size = int(resolved_args[0])
        else:
            elem_type = str(resolved_args[0])
    return elem_type, fixed_size

def resolve_c_type(type_name: str) -> str:
    t_str = str(type_name.value if hasattr(type_name, 'value') else type_name).strip()
    if t_str.endswith('*'):
        base = t_str[:-1].strip()
        return f'{resolve_c_type(base)}*'
    if t_str in CUSTOM_TYPES:
        c_val = CUSTOM_TYPES[t_str]['c_type']
        if c_val:
            return c_val
    if t_str in INTRINSIC_TYPES:
        return INTRINSIC_TYPES[t_str]
    if t_str in ('int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64'):
        return f'{t_str}_t'
    if t_str == 'integer':
        return 'int'
    if t_str == 'middle':
        return '_Float16'
    if t_str == 'chain':
        return 'char*'
    if t_str in ('type', '__arrof__'):
        return ''
    if t_str == 'str':
        return 'char*'
    if t_str in ('bool', 'boolean'):
        return 'bool'
    if t_str in ('ptr', 'pointer'):
        return 'void*'
    return t_str

def get_format_specifier(type_name: str) -> str:
    c_t = resolve_c_type(type_name)
    if c_t in ('char*', 'str') or type_name == 'chain':
        return '%s'
    if c_t in ('float', 'double', '_Float16'):
        return '%f'
    if c_t in ('int64_t', 'uint64_t', 'long long', 'unsigned long long'):
        return '%lld'
    if c_t in ('void*', 'ptr') or c_t.endswith('*'):
        return '%p'
    if c_t == 'bool':
        return '%s'
    if 'int' in c_t:
        return '%d'
    if c_t == 'char':
        return '%c'
    return '%s'

DEFAULT_BUILTINS: list[tuple[str, str]] = [
    ('int', '__int64_t__'),
    ('int8', '__int8_t__'),
    ('int16', '__int16_t__'),
    ('int32', '__int32_t__'),
    ('int64', '__int64_t__'),
    ('uint', '__uint64_t__'),
    ('uint8', '__uint8_t__'),
    ('uint16', '__uint16_t__'),
    ('uint32', '__uint32_t__'),
    ('uint64', '__uint64_t__'),
    ('float', '__float_t__'),
    ('middle', '__middle_t__'),
    ('double', '__double_t__'),
    ('char', '__char_t__'),
    ('str', '__str_t__'),
    ('bool', '__bool_t__'),
    ('ptr', '__ptr_t__'),
    ('pointer', '__void_p_t__'),
    ('void', '__void_t__'),
    ('type', '__type_t__'),
]

for _b_name, _b_intr in DEFAULT_BUILTINS:
    register_type(_b_name, _b_intr)

"""Visitor especial para emitir llamadas a funciones intrínsecas (funnames) en C.

Traduce llamadas a intrínsecos como print, sizeof, free, input y EGL_Version
a sentencias y expresiones estándar en C con sus formatos correspondientes.
"""

from typing import Any

from gram import ast
from core.initiator.reserve_funnames import MagicFuncsManager, ReservedFunc
from core.processor.objects.variable import Variable
from core.processor.visitors.utils import get_node_value


def is_intrinsic(name: str) -> bool:
    """Verifica si un nombre corresponde a una función intrínseca reservada."""
    return MagicFuncsManager.exists(name)


def _unwrap_node(node: Any) -> Any:
    while isinstance(node, ast.ASTRef) and node.nodes:
        node = node.nodes[0]
    return node


def _infer_c_format(arg: Any, storage: Any) -> tuple[str, bool]:
    """Infiere el especificador de formato C y si requiere casteo ternario para booleanos.

    Retorna:
        tuple[str, bool]: (especificador_de_formato, es_booleano)
    """
    arg = _unwrap_node(arg)

    if isinstance(arg, bool):
        return ("%s", True)

    if isinstance(arg, int):
        return ("%d", False)

    if isinstance(arg, float):
        return ("%f", False)

    if isinstance(arg, ast.ASTTokenNode):
        tok_val = str(arg.token.value) if arg.token.value is not None else ""
        if (tok_val.startswith('"') and tok_val.endswith('"')) or (tok_val.startswith("'") and tok_val.endswith("'")):
            return ("%s", False)
        if tok_val.isdigit():
            return ("%d", False)
        if tok_val.lower() in ('true', 'false'):
            return ("%s", True)
        if storage is not None:
            resolved = storage.resolve(tok_val)
            if resolved is not None and isinstance(resolved, Variable):
                return _type_to_format(resolved.type)
        return ("%s", False)

    name = str(arg)

    if (name.startswith('"') and name.endswith('"')) or (name.startswith("'") and name.endswith("'")):
        return ("%s", False)

    if name.isdigit():
        return ("%d", False)

    if name.lower() in ('true', 'false'):
        return ("%s", True)

    if storage is not None:
        resolved = storage.resolve(name)
        if resolved is not None and isinstance(resolved, Variable):
            return _type_to_format(resolved.type)

    return ("%s", False)


def _type_to_format(t: str) -> tuple[str, bool]:
    t = t.strip()
    if t in ('int', 'int32', 'int16', 'int8', 'byte'):
        return ("%d", False)
    if t in ('uint', 'uint32', 'uint16', 'uint8'):
        return ("%u", False)
    if t == 'int64':
        return ("%lld", False)
    if t == 'uint64':
        return ("%llu", False)
    if t in ('float', 'double', 'middle'):
        return ("%f", False)
    if t == 'char':
        return ("%c", False)
    if t in ('chain', 'char*'):
        return ("%s", False)
    if t == 'bool':
        return ("%s", True)
    if t in ('ptr', 'cptr') or t.endswith('*'):
        return ("%p", False)
    return ("%d", False)


def emit_print(args: list[Any], kwargs: dict[str, Any], storage: Any) -> str:
    """Traduce print(*args, sep=' ') a printf() con formatos C correspondientes."""
    from core.backend.ec.visitors.variable import resolve_value

    if not args:
        return 'printf("\\n")'

    formats: list[str] = []
    arg_exprs: list[str] = []
    sep = kwargs.get('sep', ' ')

    for arg in args:
        val_str = resolve_value(arg, storage=storage)
        fmt, is_bool = _infer_c_format(arg, storage)
        formats.append(fmt)
        if is_bool:
            arg_exprs.append(f"({val_str} ? \"true\" : \"false\")")
        else:
            arg_exprs.append(val_str)

    fmt_str = sep.join(formats) + "\\n"
    args_joined = ", ".join(arg_exprs)
    return f'printf("{fmt_str}", {args_joined})'


def emit_sizeof(args: list[Any], storage: Any) -> str:
    """Traduce sizeof(target) a sizeof(...) en C."""
    from core.backend.ec.visitors.variable import convert_type, resolve_value

    if not args:
        return 'sizeof(void*)'

    target = _unwrap_node(args[0])
    target_name = str(target.token.value) if isinstance(target, ast.ASTTokenNode) else str(target)

    if storage is not None:
        st = storage.find_struct(target_name)
        if st is not None:
            return f"sizeof({st.c_name})"
        en = storage.find_enum(target_name)
        if en is not None:
            return f"sizeof({en.c_name})"

    c_type = convert_type(target_name)
    if c_type and c_type != target_name:
        return f"sizeof({c_type})"

    val_str = resolve_value(args[0], storage=storage)
    return f"sizeof({val_str})"


def emit_free(args: list[Any], storage: Any) -> str:
    """Traduce free(ptr) a free(...) en C."""
    from core.backend.ec.visitors.variable import resolve_value

    if not args:
        return 'free(NULL)'
    val_str = resolve_value(args[0], storage=storage)
    return f"free({val_str})"


def emit_input(args: list[Any], storage: Any) -> str:
    """Traduce input(prompt) a llamada a helper _ec_input() en C."""
    from core.backend.ec.visitors.variable import resolve_value

    if args:
        prompt_str = resolve_value(args[0], storage=storage)
        return f"_ec_input({prompt_str})"
    return '_ec_input("")'


def emit_version() -> str:
    """Traduce EGL_Version() a la constante literal en tiempo de compilación."""
    return '"1.0.0"'


def visit_intrinsic(
    name: str,
    args: list[Any],
    kwargs: dict[str, Any] | None = None,
    storage: Any = None,
) -> str:
    """Despacha la emisión C para cualquier función intrínseca reservada."""
    kw = kwargs or {}
    if name == 'print':
        return emit_print(args, kw, storage)
    if name == 'sizeof':
        return emit_sizeof(args, storage)
    if name == 'free':
        return emit_free(args, storage)
    if name == 'input':
        return emit_input(args, storage)
    if name == 'EGL_Version':
        return emit_version()
    raise NotImplementedError(f"Intrínseco '{name}' no soportado en backend C.")


__all__ = [
    'is_intrinsic',
    'visit_intrinsic',
    'emit_print',
    'emit_sizeof',
    'emit_free',
    'emit_input',
    'emit_version',
]

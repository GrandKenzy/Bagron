"""Emisor de C para declaraciones de alias de tipo (Backend EC).

Traduce objetos TypeAlias a código C estándar (typedef).
"""

from core.backend.ec.visitors.variable import convert_type
from core.processor.objects.type_decl import TypeAlias


def visit_type_alias(alias_obj: TypeAlias) -> tuple[str, str | None]:
    """Genera la definición typedef en C para un alias de tipo y su cabecera.

    Retorna:
        tuple[str, str | None]: (c_code, header_code)
    """
    name = alias_obj.name
    privacy = alias_obj.privacy
    target = alias_obj.target_type.strip()

    if target.startswith('array[') and target.endswith(']'):
        inner = target[6:-1].strip()
        parts = [p.strip() for p in inner.split(',')]
        elem_type = convert_type(parts[0])
        size_str = parts[1] if len(parts) > 1 else ""
        size_part = f"[{size_str}]" if size_str else "[]"
        decl = f"typedef {elem_type} {name}{size_part};"
    elif target.endswith('*'):
        base = convert_type(target[:-1].rstrip())
        decl = f"typedef {base}* {name};"
    else:
        c_type = convert_type(target)
        decl = f"typedef {c_type} {name};"

    header = decl if privacy == 'public' else None
    return (decl, header)


__all__ = ['visit_type_alias']

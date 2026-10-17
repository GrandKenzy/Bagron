"""Emisor de C para declaraciones de enums (Backend EC).

Traduce objetos EnumDecl a código C estándar (typedef enum o constantes).
"""

from core.processor.objects.enum_decl import EnumDecl


def visit_enum(enum_obj: EnumDecl) -> tuple[str, str | None]:
    """Genera la definición en C para un enum y su encabezado correspondiente.

    Retorna:
        tuple[str, str | None]: (c_code, header_code)
    """
    name = enum_obj.c_name
    privacy = enum_obj.privacy
    items = enum_obj.items

    has_string_values = any(isinstance(v, str) for _, v in items)

    if has_string_values:
        lines = [f"typedef const char* {name};"]
        for m_name, m_val in items:
            lines.append(f'#define {name}_{m_name} "{m_val}"')
        decl = "\n".join(lines)
    elif not items:
        decl = f"typedef enum {{\n    _{name}_EMPTY = 0\n}} {name};"
    else:
        member_lines = []
        for m_name, m_val in items:
            m_ident = f"{name}_{m_name}"
            if m_val is not None:
                member_lines.append(f"    {m_ident} = {m_val}")
            else:
                member_lines.append(f"    {m_ident}")
        body = ",\n".join(member_lines)
        decl = f"typedef enum {{\n{body}\n}} {name};"

    header = decl if privacy == 'public' else None
    return (decl, header)


__all__ = ['visit_enum']

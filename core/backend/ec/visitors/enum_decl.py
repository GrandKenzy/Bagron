"""Emisor de C para declaraciones de enums (Backend EC).

Traduce objetos EnumDecl a código C estándar (typedef enum).
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

    if not items:
        decl = f"typedef enum {{\n    _{name}_EMPTY = 0\n}} {name};"
    else:
        member_lines = []
        for m_name, m_val in items:
            if m_val is not None:
                member_lines.append(f"    {m_name} = {m_val}")
            else:
                member_lines.append(f"    {m_name}")
        body = ",\n".join(member_lines)
        decl = f"typedef enum {{\n{body}\n}} {name};"

    header = decl if privacy == 'public' else None
    return (decl, header)


__all__ = ['visit_enum']
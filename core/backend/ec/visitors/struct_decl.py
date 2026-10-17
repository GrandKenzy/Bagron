"""Emisor de C para declaraciones de estructuras, molds y flags (Backend EC).

Traduce objetos StructDecl a código C estándar (typedef struct con atributos y campos).
"""

from typing import Any

from core.backend.ec.visitors.variable import convert_type
from core.processor.objects.struct_decl import StructDecl


def visit_struct(struct_obj: StructDecl, storage: Any = None) -> tuple[str, str | None]:
    """Genera la definición en C para un struct, mold o flags y su cabecera.

    Retorna:
        tuple[str, str | None]: (c_code, header_code)
    """
    name = struct_obj.c_name
    privacy = struct_obj.privacy

    packed_attr = " __attribute__((__packed__))" if struct_obj.is_packed else ""
    align_attr = f" __attribute__((aligned({struct_obj.align})))" if struct_obj.align is not None else ""
    volatile_prefix = "volatile " if struct_obj.is_volatile else ""

    if not struct_obj.fields:
        body = "    char _dummy;"
    else:
        field_lines: list[str] = []
        for field in struct_obj.fields:
            raw_field_t = field.type
            # Si el tipo del campo es un struct o tipo declarado en storage, resolver a su c_name
            if storage is not None:
                base_t = raw_field_t.rstrip('*')
                st = storage.find_struct(base_t)
                if st is not None:
                    raw_field_t = raw_field_t.replace(base_t, st.c_name)
                else:
                    en = storage.find_enum(base_t)
                    if en is not None:
                        raw_field_t = raw_field_t.replace(base_t, en.c_name)

            f_type = convert_type(raw_field_t)
            if field.fixed_size is not None:
                field_lines.append(f"    {f_type} {field.name}[{field.fixed_size}];")
            elif field.bits is not None:
                if field.name:
                    field_lines.append(f"    {f_type} {field.name} : {field.bits};")
                else:
                    field_lines.append(f"    {f_type} : {field.bits};")
            else:
                field_lines.append(f"    {f_type} {field.name};")
        body = "\n".join(field_lines)

    decl = f"typedef {volatile_prefix}struct{packed_attr}{align_attr} {{\n{body}\n}} {name};"
    header = decl if privacy == 'public' else None
    return (decl, header)


__all__ = ['visit_struct']

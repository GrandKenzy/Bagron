from typing import Any
from gram import ast
from core.processor.objects.struct_decl import StructDecl, StructField
from core.processor.storage import Storage
from core.processor.visitors.var_decl import _extract_ptr_modifier, extract_array_size, extract_type


def visit_struct(storage: Storage, node: ast.ASTRef) -> StructDecl:
    kind = node.name.lower()

    # STRUCT / MOLD / FLAGS = Seq(FIRM, BODY)

    firm: ast.ASTRef = node.nodes[0]  # type: ignore
    body: ast.ASTRef = node.nodes[1]  # type: ignore

    # 1. Privacidad y atributos de la firma
    first_tok = firm.nodes[0]
    privacy: str = first_tok.token.value if isinstance(first_tok, ast.ASTTokenNode) and first_tok.token.value in ('public', 'private') else storage.privacy  # type: ignore

    is_volatile = any(isinstance(n, ast.ASTTokenNode) and n.token.value == '__volatile__' for n in firm.nodes)

    # El IDENT siempre es el penúltimo nodo de la firma (antes de ':')
    struct_name: str = firm.nodes[-2].token.value  # type: ignore

    # 2. Verificación de colisiones
    storage.collition_name(struct_name)

    # 3. Procesar cuerpo
    items_list = body.nodes[1] if len(body.nodes) > 1 and isinstance(body.nodes[1], list) else []

    fields: list[StructField] = []
    seen_field_names: set[str] = set()
    is_packed = False
    align: int | str | None = None

    for item in items_list:
        if not isinstance(item, ast.ASTRef):
            continue

        if item.name == 'VAR_PARTIAL_DECL':
            ptr_mod, start_idx = _extract_ptr_modifier(item)
            target_node = item.nodes[start_idx]
            field_name: str = target_node.token.value
            type_node = item.nodes[start_idx + 2]
            raw_type = extract_type(type_node)
            fixed_size = extract_array_size(type_node)

            if ptr_mod == 'cptr':
                field_type = f"{raw_type}* const" if raw_type else 'cptr'
            elif ptr_mod == 'ptr':
                field_type = f"{raw_type}*" if raw_type else 'ptr'
            else:
                field_type = raw_type

            if field_name in seen_field_names:
                raise RuntimeError(f"Campo duplicado '{field_name}' en {kind} '{struct_name}'.")

            seen_field_names.add(field_name)
            fields.append(StructField(name=field_name, type=field_type, fixed_size=fixed_size))

        elif item.name == 'VAR_PTR_GENERIC_PARTIAL':
            ptr_mod = item.nodes[0].nodes[0].token.value
            target_node = item.nodes[1]
            field_name: str = target_node.token.value
            field_type = ptr_mod
            if field_name in seen_field_names:
                raise RuntimeError(f"Campo duplicado '{field_name}' en {kind} '{struct_name}'.")
            seen_field_names.add(field_name)
            fields.append(StructField(name=field_name, type=field_type, fixed_size=None))

        elif item.name == 'BITFIELD_ITEM':
            field_type = extract_type(item.nodes[0])  # type: ignore
            has_name = len(item.nodes) == 4
            field_name = item.nodes[1].token.value if has_name else ""  # type: ignore
            bits = int(item.nodes[-1].token.value)  # type: ignore

            if field_name:
                if field_name in seen_field_names:
                    raise RuntimeError(f"Campo duplicado '{field_name}' en {kind} '{struct_name}'.")
                seen_field_names.add(field_name)

            fields.append(StructField(name=field_name, type=field_type, bits=bits))

        elif item.name in ('STRUCT_PACKED', 'MOLD_PACKED'):
            is_packed = True

        elif item.name in ('STRUCT_ALIGN', 'MOLD_ALIGN'):
            if len(item.nodes) > 1 and isinstance(item.nodes[1], ast.ASTTokenNode):
                val = item.nodes[1].token.value
                align = int(val) if isinstance(val, (int, str)) and str(val).isdigit() else val

    return storage.add_struct(
        name=struct_name,
        fields=fields,
        privacy=privacy,
        is_packed=is_packed,
        is_volatile=is_volatile,
        align=align,
        kind=kind,
    )


__all__ = [
    'visit_struct',
]

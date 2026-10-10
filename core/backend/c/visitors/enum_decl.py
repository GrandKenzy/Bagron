from core.processor.objects.enum_decl import EnumDecl
import core.backend.c as c_backend

def visit(enum_obj: EnumDecl):
    item_lines = []
    for item_name, item_val in enum_obj.items:
        if item_val is not None:
            item_lines.append(f"    {item_name} = {item_val}")
        else:
            item_lines.append(f"    {item_name}")

    items_body = ",\n".join(item_lines)
    if items_body:
        typedef_def = f"typedef enum {enum_obj.name} {{\n{items_body}\n}} {enum_obj.name};"
    else:
        typedef_def = f"typedef enum {enum_obj.name} {{\n    __dummy_{enum_obj.name}\n}} {enum_obj.name};"
    c_backend.add_typedef(typedef_def)

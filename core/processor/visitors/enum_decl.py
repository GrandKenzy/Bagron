from typing import Any
import gram
from core.processor.objects.enum_decl import EnumDecl
from core.processor.type_system import register_type

def visit(node: gram.ASTNode) -> EnumDecl:
    vals = [str(v.value if hasattr(v, 'value') else v) for v in node.values]
    privacy = 'private' if 'private' in vals else 'public'
    name = vals[-1]

    items: list[tuple[str, Any]] = []
    enum_members: dict[str, str] = {}
    for item_node in node.find('EGL_ENUM_ITEM'):
        item_name = str(item_node.values[0])
        val_nodes = item_node.find('EGL_ENUM_VALUE')
        item_val = None
        if val_nodes:
            all_toks = getattr(val_nodes[0], 'all_tokens', val_nodes[0].values)
            item_val = ''.join(str(getattr(t, 'value', t)) for t in all_toks)
        items.append((item_name, item_val))
        enum_members[item_name] = item_name
        if item_name.startswith('inmodule_'):
            parts = item_name.split('_', 2)
            if len(parts) >= 3:
                short_name = parts[-1]
                enum_members[short_name] = item_name

    entry = register_type(name, name)
    entry['is_enum'] = True
    entry['enum_members'] = enum_members

    enum_obj = EnumDecl(name=name, items=items, privacity=privacy)
    return enum_obj

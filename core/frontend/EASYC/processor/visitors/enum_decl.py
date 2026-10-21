from typing import Any
from gram import ast
from core.processor.objects.enum_decl import EnumDecl
from core.processor.storage import Storage


def _extract_item_value(val_ref: ast.ASTRef) -> Any:
    target = val_ref.nodes[-1]
    if isinstance(target, ast.LiteralNumber):
        val = target.token.value
        if len(val_ref.nodes) == 2 and isinstance(val_ref.nodes[0], ast.ASTTokenNode) and 'MINUS' in str(val_ref.nodes[0].token.token):
            return -val
        return val

    if isinstance(target, ast.LiteralString):
        return target.token.value.strip('"\'')

    if isinstance(target, ast.ASTTokenNode):
        return target.token.value

    return str(target)


def visit_enum(storage: Storage, node: ast.ASTRef) -> EnumDecl:
    # Privacidad opcional

    privacy: str = node.nodes[0].token.value if len(node.nodes) == 5 else storage.privacy  # type: ignore

    # Nombre del enum
    enum_name: str = node.nodes[-3].token.value  # type: ignore

    # Verificación de colisiones
    storage.collition_name(enum_name)

    # ENUM_BODY
    body: ast.ASTRef = node.nodes[-1]  # type: ignore
    items_list = body.nodes[1] if len(body.nodes) > 1 and isinstance(body.nodes[1], list) else []

    items: list[tuple[str, Any]] = []
    current_auto_value = 0

    for item in items_list:
        if isinstance(item, ast.ASTRef) and item.name == 'ENUM_ITEM':
            member_name: str = item.nodes[0].token.value  # type: ignore

            if len(item.nodes) > 1 and item.nodes[1] and isinstance(item.nodes[1], list):
                val_seq = item.nodes[1]
                if len(val_seq) > 1 and isinstance(val_seq[1], ast.ASTRef):
                    member_value = _extract_item_value(val_seq[1])
                    if isinstance(member_value, int):
                        current_auto_value = member_value + 1
                else:
                    member_value = current_auto_value
                    current_auto_value += 1
            else:
                member_value = current_auto_value
                current_auto_value += 1

            items.append((member_name, member_value))

    return storage.add_enum(enum_name, items, privacy)


__all__ = [
    'visit_enum',
]

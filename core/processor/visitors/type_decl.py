from typing import Any

from gram import ast

from core.processor.objects.function import LocalStorage
from core.processor.objects.type_decl import TypeAlias
from core.processor.storage import Storage
from core.processor.visitors.var_decl import extract_type


def visit_typealias(storage: Any, node: ast.ASTRef) -> TypeAlias:
    # TypeAlias solo puede ser declarado a nivel global

    if isinstance(storage, LocalStorage):
        func_name = storage.function.name if storage.function else 'anónima'
        raise RuntimeError(f"TypeAlias solo puede ser declarado a nivel global, no dentro de la función '{func_name}'.")

    if not isinstance(storage, Storage):
        raise RuntimeError("TypeAlias solo puede ser declarado a nivel global, fuera de bloques o funciones.")

    # node.nodes para TYPEALIAS:
    # Sin privacidad: [KEYWORD('TypeAlias'), SEGMENT_TYPE, IDENT]
    # Con privacidad: [TOKEN('public'|'private'), KEYWORD('TypeAlias'), SEGMENT_TYPE, IDENT]
    if (
        len(node.nodes) >= 4
        and isinstance(node.nodes[0], ast.ASTTokenNode)
        and node.nodes[0].token.value in ('public', 'private')
    ):
        privacy = node.nodes[0].token.value
        type_node = node.nodes[2]
        ident_node = node.nodes[3]
    else:
        privacy = storage.privacy
        type_node = node.nodes[1]
        ident_node = node.nodes[2]

    alias_name = ident_node.token.value # type: ignore
    target_type = extract_type(type_node) # type: ignore

    # Validar colisión en Storage
    storage.collition_name(alias_name)

    # Registrar el alias de tipo en Storage
    alias_obj = storage.add_type_alias(alias_name, target_type, privacy)
    return alias_obj


__all__ = [
    'visit_typealias',
]

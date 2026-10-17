from gram import ast

from core.processor.storage import Storage


def visit_clause(storage: Storage, node: ast.ASTRef):
    target = str(node.nodes[1].token.value).lower()  # type: ignore
    raw = node.nodes[2].token.value  # type: ignore

    if target == 'arch':
        storage.arch = str(raw).strip('"\'')
    elif target == 'system':
        storage.system = str(raw).strip('"\'')
    elif target == 'visibility':
        storage.privacy = str(raw).strip('"\'')
    elif target == 'stacklimit':
        storage.stacklimit = int(raw)



__all__ = [
    'visit_clause',
]
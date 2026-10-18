from gram import ast

from core.processor.storage import Storage


def visit_struct(storage: Storage, node: ast.ASTRef):
    print(node)


__all__ = [
    'visit_struct'
]
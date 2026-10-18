from gram import ast

from core.processor.storage import Storage


def visit_class(storage: Storage, node: ast.ASTRef):
    print(node)


__all__ = [
    'visit_class'
]
"""Visitor vacío para clases en el backend EC."""
from typing import Any


def visit_class(class_obj: Any) -> tuple[str, str | None]:
    return ('', None)


__all__ = ['visit_class']

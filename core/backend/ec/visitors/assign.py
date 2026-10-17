"""Emisor de C para sentencias de asignación y reasignación (Backend EC).

Traduce objetos Assign a sentencias de C válidas (ej: a = 20;, a += 5;).
"""

from typing import Any
from core.backend.ec.visitors.variable import resolve_value
from core.processor.objects.assign import Assign
from core.processor.objects.variable import Variable


def visit_assign(assign_obj: Assign, storage: Any = None) -> str:
    """Genera la sentencia C para una asignación o reasignación.

    Retorna:
        str: Línea de código en C terminada en ';' (ej: '_ec_main_..._a = 30;').
    """
    target = assign_obj.target
    op = assign_obj.op
    value = assign_obj.value

    # 1. Determinar el nombre/identificador del destino
    if isinstance(target, str):
        # Si es un identificador simple en storage, usar su c_name con mangling
        if storage is not None:
            resolved = storage.resolve(target)
            if resolved is not None and isinstance(resolved, Variable):
                target_str = resolved.c_name
            else:
                target_str = target
        else:
            target_str = target
    else:
        target_str = resolve_value(target, storage=storage)

    # 2. Resolver el valor de la asignación
    val_str = resolve_value(value, storage=storage)

    return f"{target_str} {op} {val_str};"


__all__ = ['visit_assign']

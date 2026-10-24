# Reexportacion de tools para acceso directo desde core.frontend.HEADERS.tools
from core.frontend.HEADERS.headers.tools import (
    common,
    func_type_resolution,
    object_type_resolution,
    var_type_resolution,
)

__all__ = [
    'common',
    'func_type_resolution',
    'object_type_resolution',
    'var_type_resolution',
]

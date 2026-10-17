from core.initiator.rules.call import *
from core.initiator.rules.class_decl import *
from core.initiator.rules.clauses import *
from core.initiator.rules.enum_decl import *
from core.initiator.rules.expression import *
from core.initiator.rules.flags_decl import *
from core.initiator.rules.func_decl import *
from core.initiator.rules.imports import *
from core.initiator.rules.loops import *
from core.initiator.rules.mold_decl import *
from core.initiator.rules.statement import *
from core.initiator.rules.struct_decl import *
from core.initiator.rules.type_decl import *
from core.initiator.rules.value import *
from core.initiator.rules.var_decl import *

from core.initiator.rules import (
    call,
    class_decl,
    clauses,
    enum_decl,
    expression,
    flags_decl,
    func_decl,
    imports,
    loops,
    mold_decl,
    statement,
    struct_decl,
    type_decl,
    value,
    var_decl,
)

# Retrocompatibility aliases
EGL_CLAUSE = CLAUSE

__all__ = [
    *call.__all__,
    *class_decl.__all__,
    *clauses.__all__,
    *enum_decl.__all__,
    *expression.__all__,
    *flags_decl.__all__,
    *func_decl.__all__,
    *imports.__all__,
    *loops.__all__,
    *mold_decl.__all__,
    *statement.__all__,
    *struct_decl.__all__,
    *type_decl.__all__,
    *value.__all__,
    *var_decl.__all__,
    'EGL_CLAUSE',
]
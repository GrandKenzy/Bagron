from gram import combinators as cmb

from core.frontend.HEADERS.headers.syntax.items.attributes import STATIC_ASSERT_DECL
from core.frontend.HEADERS.headers.syntax.items.declarators import TYPE
from core.frontend.HEADERS.headers.syntax.items.enum_decl import TAG_DECL
from core.frontend.HEADERS.headers.syntax.items.func_decl import FUNC_DECL
from core.frontend.HEADERS.headers.syntax.items.typedef_decl import (
    EMPTY_DECL,
    TYPEDEF_DECL,
    TYPE_DECL,
)
from core.frontend.HEADERS.headers.syntax.items.var_decl import VAR_DECL


class ENTRYPOINT(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(STATIC_ASSERT_DECL),
        cmb.Ref(TYPEDEF_DECL),
        cmb.Ref(FUNC_DECL),
        cmb.Ref(VAR_DECL),
        cmb.Ref(TAG_DECL),
        cmb.Ref(TYPE_DECL),
        cmb.Ref(EMPTY_DECL),
    )


from core.frontend.HEADERS.headers.syntax import HEADERS_SESSION

HEADERS_SESSION.entrypoint = ENTRYPOINT

__all__ = [
    'ENTRYPOINT',
    'HEADERS_SESSION',
    'TYPE',
]
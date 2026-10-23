from gram import combinators as cmb

from core.frontend.HEADERS.headers.syntax.items.values import TYPE


class ENTRYPOINT(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(TYPE)
    )
    
    
from core.frontend.HEADERS.headers.syntax import HEADERS_SESSION

HEADERS_SESSION.entrypoint = ENTRYPOINT

__all__ = [
    'ENTRYPOINT',
    'HEADERS_SESSION'
]
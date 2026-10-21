from gram import combinators as cmb

from core.frontend.EASYC.syntax.items.value import ARGUMENTS


class CALL(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Ref(ARGUMENTS)
    )
    
__all__ = ['CALL']
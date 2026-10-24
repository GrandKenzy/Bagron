from gram import combinators as cmb

from core.frontend.C.syntax.items.value import ARGUMENTS


class CALL(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Ref(ARGUMENTS)
    )


class CALL_STMT(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Ref(CALL),
        cmb.MatchToken('SEMICOLON')
    )


__all__ = [
    'CALL',
    'CALL_STMT',
]

from gram import combinators as cmb
from gram import lexer

from core.initiator.rules.value import ARGUMENTS, VALUE


class TYPE_MEMBER(cmb.RuleItem):
    entrypoint = cmb.MatchGroup('types')
    nodeable = True


class CALL(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Alt(
            cmb.MatchToken('IDENT'),
            cmb.MatchKeyword('sizeof'),
        ),
        cmb.Ref(ARGUMENTS),
    )
    nodeable = True


class MEMBER_CHAIN(cmb.RuleItem):
    entrypoint = cmb.Separator(
        sep=lexer.Token.DOT,
        values=[
            cmb.Ref(CALL),
            cmb.MatchToken('IDENT'),
            cmb.Ref(TYPE_MEMBER),
        ],
        min=2,
    )
    nodeable = True


class INDEX_ACCESS(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Alt(
            cmb.Ref(MEMBER_CHAIN),
            cmb.Ref(CALL),
            cmb.MatchToken('IDENT'),
        ),
        cmb.Some(
            cmb.Enclosed(
                open=lexer.Token.LBRACKET,
                close=lexer.Token.RBRACKET,
                content=cmb.Ref(VALUE),
            )
        ),
    )
    nodeable = True


__all__ = [
    'TYPE_MEMBER',
    'CALL',
    'MEMBER_CHAIN',
    'INDEX_ACCESS',
]
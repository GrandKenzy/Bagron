from gram import combinators as cmb
from gram import lexer

from core.initiator.rules.call import CALL
from core.initiator.rules.value import RETURN, VALUE
from core.initiator.rules.var_decl import VAR_ASSIGNATION, VAR_DECL


class WHILE(cmb.RuleItem):
    nodeable = True


class FOR(cmb.RuleItem):
    nodeable = True


class WHILE_CONDITION(cmb.RuleItem):
    entrypoint = cmb.Ref(VALUE)
    nodeable = True


class SKIPER(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchGroup('skipers'),  # continue, break
    )
    nodeable = True


class WHILE_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(CALL),
                cmb.Ref(VAR_DECL),
                cmb.Ref(VAR_ASSIGNATION),
                cmb.Ref(WHILE),
                cmb.Ref(FOR),
                cmb.Ref(RETURN),
                cmb.Ref(SKIPER),
                cmb.MatchKeyword('pass'),
            )
        ),
        cmb.MatchToken('DEDENT'),
    )
    nodeable = True


WHILE.entrypoint = cmb.Seq(
    cmb.MatchKeyword('while'),
    cmb.Ref(WHILE_CONDITION),
    cmb.MatchToken('COLON'),
    cmb.Ref(WHILE_BODY),
)


class FOR_TARGETS(cmb.RuleItem):
    entrypoint = cmb.Separator(
        sep=lexer.Token.COMMA,
        values=[cmb.MatchToken('IDENT')],
    )
    nodeable = True


class ITERABLE_GROUP(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.Separator(
            sep=lexer.Token.COMMA,
            values=[cmb.Ref(VALUE)],
        ),
    )
    nodeable = True


class ITERABLE(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(ITERABLE_GROUP),
        cmb.Ref(VALUE),
    )
    nodeable = True


class FOR_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(CALL),
                cmb.Ref(VAR_DECL),
                cmb.Ref(VAR_ASSIGNATION),
                cmb.Ref(WHILE),
                cmb.Ref(FOR),
                cmb.Ref(RETURN),
                cmb.Ref(SKIPER),
                cmb.MatchKeyword('pass'),
            )
        ),
        cmb.MatchToken('DEDENT'),
    )
    nodeable = True


FOR.entrypoint = cmb.Seq(
    cmb.MatchKeyword('for'),
    cmb.Ref(FOR_TARGETS),
    cmb.MatchGroup('iters'),
    cmb.Ref(ITERABLE),
    cmb.MatchToken('COLON'),
    cmb.Ref(FOR_BODY),
)


__all__ = [
    'FOR',
    'FOR_BODY',
    'FOR_TARGETS',
    'ITERABLE',
    'ITERABLE_GROUP',
    'SKIPER',
    'WHILE',
    'WHILE_BODY',
    'WHILE_CONDITION',
]

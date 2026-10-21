from gram import combinators as cmb

from core.initiator.rules.call import CALL, MEMBER_CHAIN
from core.initiator.rules.loops import FOR, WHILE
from core.initiator.rules.statement import IF
from core.initiator.rules.value import PARAMETERS, RETURN, SEGMENT_TYPE
from core.initiator.rules.var_decl import VAR_ASSIGNATION, VAR_DECL


class DECORATOR(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('AT'),
        cmb.MatchToken('IDENT'),
    )
    nodeable = True


class DECORATORS(cmb.RuleItem):
    entrypoint = cmb.Many(cmb.Ref(DECORATOR))
    nodeable = True


class FUNCTION_FIRM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.Opt(cmb.MatchKeyword('__inline__')),
        cmb.Ref(SEGMENT_TYPE),
        cmb.MatchToken('IDENT'),
        cmb.Ref(PARAMETERS),
        cmb.MatchToken('COLON'),
    )
    nodeable = True


class FUNCTION_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(IF),
                cmb.Ref(WHILE),
                cmb.Ref(FOR),
                cmb.Ref(VAR_DECL),
                cmb.Ref(VAR_ASSIGNATION),
                cmb.Ref(MEMBER_CHAIN),
                cmb.Ref(CALL),
                cmb.Ref(RETURN),
                cmb.MatchKeyword('pass'),
            )
        ),
        cmb.MatchToken('DEDENT'),
    )
    nodeable = True


class FUNCTION(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(FUNCTION_FIRM),
        cmb.Ref(FUNCTION_BODY),
    )
    nodeable = True


class DECORATED_FUNCTION(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(DECORATORS),
        cmb.Ref(FUNCTION),
    )
    nodeable = True


__all__ = [
    'DECORATOR',
    'DECORATORS',
    'FUNCTION_FIRM',
    'FUNCTION_BODY',
    'FUNCTION',
    'DECORATED_FUNCTION',
]
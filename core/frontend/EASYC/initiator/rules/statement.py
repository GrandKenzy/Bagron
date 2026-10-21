from gram import combinators as cmb

from core.initiator.rules.call import CALL, MEMBER_CHAIN
from core.initiator.rules.loops import FOR, SKIPER, WHILE
from core.initiator.rules.value import RETURN, VALUE
from core.initiator.rules.var_decl import VAR_ASSIGNATION, VAR_DECL


class IF(cmb.RuleItem):
    nodeable = True


class CONDITION(cmb.RuleItem):
    entrypoint = cmb.Ref(VALUE)
    nodeable = True


class IF_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(VAR_DECL),
                cmb.Ref(VAR_ASSIGNATION),
                cmb.Ref(MEMBER_CHAIN),
                cmb.Ref(CALL),
                cmb.Ref(WHILE),
                cmb.Ref(FOR),
                cmb.Ref(IF),
                cmb.Ref(RETURN),
                cmb.Ref(SKIPER),
                cmb.MatchKeyword('pass'),
            )
        ),
        cmb.MatchToken('DEDENT'),
    )
    nodeable = True


class ELIF(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('elif'),
        cmb.Ref(CONDITION),
        cmb.MatchToken('COLON'),
        cmb.Ref(IF_BODY),
    )
    nodeable = True


class ELSE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('else'),
        cmb.MatchToken('COLON'),
        cmb.Ref(IF_BODY),
    )
    nodeable = True


IF.entrypoint = cmb.Seq(
    cmb.MatchKeyword('if'),
    cmb.Ref(CONDITION),
    cmb.MatchToken('COLON'),
    cmb.Ref(IF_BODY),
    cmb.Many(cmb.Ref(ELIF)),
    cmb.Opt(cmb.Ref(ELSE)),
)


__all__ = [
    'CONDITION',
    'ELIF',
    'ELSE',
    'IF',
    'IF_BODY',
]
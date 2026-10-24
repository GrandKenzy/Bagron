from gram import combinators as cmb

from core.frontend.C.syntax.items.statements import STATEMENT_BLOCK
from core.frontend.C.syntax.items.value import PARAMETERS, POINTER, TYPE


class FUNCTION_SPECIFIERS(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Some(
        cmb.Alt(
            cmb.MatchKeyword('static'),
            cmb.MatchKeyword('inline'),
            cmb.MatchKeyword('extern'),
        )
    )


class FUNCTION_SIGNATURE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.Ref(FUNCTION_SPECIFIERS)),
        cmb.Ref(TYPE),
        cmb.Opt(cmb.Ref(POINTER)),
        cmb.MatchToken('IDENT'),
        cmb.Ref(PARAMETERS),
    )


class FUNCTION_PROTOTYPE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Ref(FUNCTION_SIGNATURE),
        cmb.MatchToken('SEMICOLON')
    )


class FUNCTION(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Alt(
        cmb.Seq(
            cmb.Ref(FUNCTION_SIGNATURE),
            cmb.Ref(STATEMENT_BLOCK)
        ),
        cmb.Ref(FUNCTION_PROTOTYPE)
    )


__all__ = [
    'FUNCTION',
    'FUNCTION_PROTOTYPE',
    'FUNCTION_SIGNATURE',
    'FUNCTION_SPECIFIERS',
]

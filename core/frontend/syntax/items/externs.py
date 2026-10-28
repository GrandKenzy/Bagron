from gram import combinators as cmb

from core.frontend.syntax.items.value import PARAMETERS, POINTER, TYPE


class EXTERN_RETURN(cmb.RuleItem):
    """Return type of an external declaration.

    Scalar returns use ``) int32``.  Pointer returns use the same declarator
    boundary as parameters: ``) *: void``.
    """

    entrypoint = cmb.Seq(
        cmb.Opt(
            cmb.Seq(
                cmb.Ref(POINTER),
                cmb.MatchToken('COLON'),
            )
        ),
        cmb.Ref(TYPE),
    )
    nodeable = True


class EXTERN_FUNCTION(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Ref(PARAMETERS),
        cmb.Ref(EXTERN_RETURN),
    )
    nodeable = True


class EXTERN_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(cmb.Ref(EXTERN_FUNCTION)),
        cmb.MatchToken('DEDENT'),
    )
    nodeable = True


class EXTERN(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('extern'),
        cmb.MatchToken('STRING'),
        cmb.MatchToken('COLON'),
        cmb.Ref(EXTERN_BODY),
    )
    nodeable = True


__all__ = [
    'EXTERN',
    'EXTERN_BODY',
    'EXTERN_FUNCTION',
    'EXTERN_RETURN',
]

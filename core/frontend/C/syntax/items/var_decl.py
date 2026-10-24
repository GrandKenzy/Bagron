from gram import combinators as cmb

from core.frontend.C.syntax.items.value import POINTER, QUALIFIER, TYPE, VALUE


class ASSIGN_OPERATOR(cmb.RuleItem):
    nodeable = False
    entrypoint = cmb.Alt(
        cmb.MatchToken('ASSIGN'),
        cmb.MatchToken('PLUS_ASSIGN'),
        cmb.MatchToken('MINUS_ASSIGN'),
        cmb.MatchToken('STAR_ASSIGN'),
        cmb.MatchToken('SLASH_ASSIGN'),
        cmb.MatchToken('PERCENT_ASSIGN'),
        cmb.MatchToken('AND_ASSIGN'),
        cmb.MatchToken('OR_ASSIGN'),
        cmb.MatchToken('XOR_ASSIGN'),
        cmb.MatchToken('SHL_ASSIGN'),
        cmb.MatchToken('SHR_ASSIGN'),
    )


class STORAGE_SPECIFIER(cmb.RuleItem):
    nodeable = False
    entrypoint = cmb.Alt(
        cmb.MatchKeyword('static'),
        cmb.MatchKeyword('extern'),
        cmb.MatchKeyword('auto'),
        cmb.MatchKeyword('register'),
    )


class VAR_DECLARATION(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.Some(cmb.Alt(
            cmb.Ref(STORAGE_SPECIFIER),
            cmb.Ref(QUALIFIER),
        ))),
        cmb.Ref(TYPE),
        cmb.Opt(cmb.Ref(POINTER)),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('ASSIGN'),
        cmb.Ref(VALUE),
        cmb.MatchToken('SEMICOLON'),
    )


class VAR_INITIALIZATION(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.Some(cmb.Alt(
            cmb.Ref(STORAGE_SPECIFIER),
            cmb.Ref(QUALIFIER),
        ))),
        cmb.Ref(TYPE),
        cmb.Opt(cmb.Ref(POINTER)),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('SEMICOLON'),
    )


class VAR(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Alt(
        cmb.Ref(VAR_DECLARATION),
        cmb.Ref(VAR_INITIALIZATION),
    )


class VAR_ASSIGNATION(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Ref(ASSIGN_OPERATOR),
        cmb.Ref(VALUE),
        cmb.MatchToken('SEMICOLON'),
    )


class VAR_INLINE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.Some(cmb.Alt(
            cmb.Ref(STORAGE_SPECIFIER),
            cmb.Ref(QUALIFIER),
        ))),
        cmb.Ref(TYPE),
        cmb.Opt(cmb.Ref(POINTER)),
        cmb.MatchToken('IDENT'),
        cmb.Opt(
            cmb.Seq(
                cmb.MatchToken('ASSIGN'),
                cmb.Ref(VALUE)
            )
        )
    )


class VAR_ASSIGNATION_NO_SEMI(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Ref(ASSIGN_OPERATOR),
        cmb.Ref(VALUE),
    )


__all__ = [
    'ASSIGN_OPERATOR',
    'STORAGE_SPECIFIER',
    'VAR',
    'VAR_ASSIGNATION',
    'VAR_ASSIGNATION_NO_SEMI',
    'VAR_DECLARATION',
    'VAR_INITIALIZATION',
    'VAR_INLINE',
]

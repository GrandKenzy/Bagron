from gram import combinators as cmb

from core.frontend.EASYC.syntax.items.value import POINTER, TYPE, VALUE


class ASSIGN_OPERATOR(cmb.RuleItem):
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
    nodeable = False


# class ASSIGN_TARGET(cmb.RuleItem):
#     entrypoint = cmb.Alt(
#         cmb.Ref(INDEX_ACCESS),
#         cmb.Ref(MEMBER_CHAIN),
#         cmb.MatchToken('IDENT'),
#     )
#     nodeable = False


class VAR_DECLARATION(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchKeyword('const')),
        cmb.MatchToken('IDENT'),
        cmb.Opt(cmb.Ref(POINTER)),
        cmb.MatchToken('COLON'),
        cmb.Ref(TYPE),
        cmb.MatchToken('ASSIGN'),
        cmb.Ref(VALUE),
    )
    nodeable = True


class VAR_INITIALIZATION(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchKeyword('const')),
        cmb.MatchToken('IDENT'),
        cmb.Opt(cmb.Ref(POINTER)),
        cmb.MatchToken('COLON'),
        cmb.Ref(TYPE),
    )
    nodeable = True


# TODO: Revisar integración de asignaciones múltiples.
# class VAR_MULTI_DECL(cmb.RuleItem):
#     entrypoint = cmb.Seq(
#         cmb.Opt(cmb.Ref(PTR_MODIFIER)),
#         cmb.Separator(
#             values=cmb.MatchToken('IDENT'),
#             min=2,
#             allow_trailing=False,
#         ),
#         cmb.MatchToken('COLON'),
#         cmb.Ref(SEGMENT_TYPE),
#         cmb.MatchToken('ASSIGN'),
#         cmb.Separator(
#             values=cmb.Ref(VALUE),
#             min=1,
#             allow_trailing=False,
#         ),
#     )
#     nodeable = True


class VAR(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.Alt(
            cmb.Ref(VAR_DECLARATION),
            cmb.Ref(VAR_INITIALIZATION)
        ),
    )
    nodeable = True


class VAR_ASSIGNATION(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Ref(ASSIGN_OPERATOR),
        cmb.Ref(VALUE),
    )
    nodeable = True


__all__ = [
    'VAR',
    'VAR_ASSIGNATION',
    'VAR_DECLARATION',
    'VAR_INITIALIZATION'
]
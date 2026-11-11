from gram import combinators as cmb
from gram import lexer

from core.frontend.syntax.items.value import TYPE


# Miembros de enumeraciones nominales.
# El delimitador entre miembros es la coma ',', pero la coma final en el último miembro es opcional.
class ENUM_ITEM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Opt(
            cmb.Seq(
                cmb.MatchToken('ASSIGN'),
                cmb.Opt(cmb.MatchToken('MINUS')),
                cmb.MatchToken('NUMBER'),
            )
        ),
    )
    nodeable = True


class ENUM_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Alt(
            cmb.Separator(
                values=cmb.Ref(ENUM_ITEM),
                sep=lexer.Token.COMMA,
                min=1,
                allow_trailing=True,
            ),
            cmb.MatchKeyword('pass'),
        ),
        cmb.MatchToken('DEDENT'),
    )
    nodeable = True


class ENUM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.MatchKeyword('enum'),
        cmb.MatchToken('IDENT'),
        cmb.Opt(cmb.Ref(TYPE)),
        cmb.MatchToken('COLON'),
        cmb.Ref(ENUM_BODY),
    )
    nodeable = True


__all__ = [
    'ENUM',
]

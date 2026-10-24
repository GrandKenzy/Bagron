from gram import combinators as cmb
from gram.core.lexer import Token

from core.frontend.HEADERS.headers.syntax.items.attributes import ATTRIBUTE_SPECIFIER
from core.frontend.HEADERS.headers.syntax.items.declarators import GENERAL_DECLARATOR
from core.frontend.HEADERS.headers.syntax.items.expressions import CONST_EXPR
from core.frontend.HEADERS.headers.syntax.items.specifiers import DECL_SPECIFIERS


class INITIALIZER(cmb.RuleItem):
    pass


class DESIGNATOR(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Seq(
            cmb.MatchToken('DOT'),
            cmb.MatchToken('IDENT')
        ),
        cmb.Enclosed(
            open=Token.LBRACKET,
            close=Token.RBRACKET,
            content=cmb.Ref(CONST_EXPR)
        )
    )
    nodeable = True


class INITIALIZER_ITEM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(
            cmb.Seq(
                cmb.Some(cmb.Ref(DESIGNATOR)),
                cmb.MatchToken('ASSIGN')
            )
        ),
        cmb.Ref(INITIALIZER)
    )
    nodeable = True


class INITIALIZER_LIST(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=Token.LBRACE,
        close=Token.RBRACE,
        content=cmb.Opt(
            cmb.Separator(
                sep=Token.COMMA,
                values=[cmb.Ref(INITIALIZER_ITEM)],
                min=1,
                allow_trailing=True
            )
        ),
        allow_empty=True
    )
    nodeable = True


INITIALIZER.entrypoint = cmb.Alt(
    cmb.Ref(INITIALIZER_LIST),
    cmb.Ref(CONST_EXPR)
)
INITIALIZER.nodeable = True


class VAR_DECLARATOR(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(GENERAL_DECLARATOR),
        cmb.Many(cmb.Ref(ATTRIBUTE_SPECIFIER)),
        cmb.Opt(
            cmb.Seq(
                cmb.MatchToken('ASSIGN'),
                cmb.Ref(INITIALIZER)
            )
        )
    )
    nodeable = True


class VAR_DECL(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(DECL_SPECIFIERS),
        cmb.Separator(
            sep=Token.COMMA,
            values=[cmb.Ref(VAR_DECLARATOR)],
            min=1
        ),
        cmb.Many(cmb.Ref(ATTRIBUTE_SPECIFIER)),
        cmb.MatchToken('SEMICOLON')
    )
    nodeable = True


__all__ = [
    'DESIGNATOR',
    'INITIALIZER',
    'INITIALIZER_ITEM',
    'INITIALIZER_LIST',
    'VAR_DECL',
    'VAR_DECLARATOR',
]

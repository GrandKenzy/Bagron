from gram import combinators as cmb
from gram.core.lexer import Token

from core.frontend.HEADERS.headers.syntax.items.attributes import ATTRIBUTE_SPECIFIER
from core.frontend.HEADERS.headers.syntax.items.declarators import (
    DECLARATOR_MODIFIER,
    DECLARATOR_SUFFIX,
    PARAMS,
    POINTER,
)
from core.frontend.HEADERS.headers.syntax.items.specifiers import DECL_SPECIFIERS


class FUNC_IDENT(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.MatchToken('IDENT'),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Seq(
                cmb.Many(cmb.Ref(DECLARATOR_MODIFIER)),
                cmb.MatchToken('IDENT')
            )
        )
    )
    nodeable = True


class FUNC_DECLARATOR(cmb.RuleItem):
    pass


FUNC_DECLARATOR.entrypoint = cmb.Seq(
    cmb.Opt(cmb.Ref(POINTER)),
    cmb.Many(cmb.Ref(DECLARATOR_MODIFIER)),
    cmb.Alt(
        cmb.Seq(
            cmb.Ref(FUNC_IDENT),
            cmb.Ref(PARAMS),
            cmb.Many(cmb.Ref(DECLARATOR_SUFFIX))
        ),
        cmb.Seq(
            cmb.Enclosed(
                open=Token.LPAREN,
                close=Token.RPAREN,
                content=cmb.Ref(FUNC_DECLARATOR)
            ),
            cmb.Some(cmb.Ref(DECLARATOR_SUFFIX))
        )
    )
)
FUNC_DECLARATOR.nodeable = True


class FUNC_DECL(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(DECL_SPECIFIERS),
        cmb.Ref(FUNC_DECLARATOR),
        cmb.Many(cmb.Ref(ATTRIBUTE_SPECIFIER)),
        cmb.MatchToken('SEMICOLON')
    )
    nodeable = True


__all__ = [
    'FUNC_DECL',
    'FUNC_DECLARATOR',
    'FUNC_IDENT',
]

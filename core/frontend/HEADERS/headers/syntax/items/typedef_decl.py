from gram import combinators as cmb
from gram.core.lexer import Token

from core.frontend.HEADERS.headers.syntax.items.attributes import ATTRIBUTE_SPECIFIER
from core.frontend.HEADERS.headers.syntax.items.declarators import GENERAL_DECLARATOR, TYPE
from core.frontend.HEADERS.headers.syntax.items.specifiers import DECL_SPECIFIERS


class TYPEDEF_DECL(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Many(cmb.Ref(ATTRIBUTE_SPECIFIER)),
        cmb.MatchKeyword('typedef'),
        cmb.Ref(DECL_SPECIFIERS),
        cmb.Separator(
            sep=Token.COMMA,
            values=[cmb.Ref(GENERAL_DECLARATOR)],
            min=1
        ),
        cmb.Many(cmb.Ref(ATTRIBUTE_SPECIFIER)),
        cmb.MatchToken('SEMICOLON')
    )
    nodeable = True


class TYPE_DECL(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(TYPE),
        cmb.Opt(cmb.MatchToken('SEMICOLON'))
    )
    nodeable = True


class EMPTY_DECL(cmb.RuleItem):
    entrypoint = cmb.MatchToken('SEMICOLON')
    nodeable = True


__all__ = [
    'EMPTY_DECL',
    'TYPEDEF_DECL',
    'TYPE_DECL',
]

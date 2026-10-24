from gram import combinators as cmb
from gram.core.lexer import Token

from core.frontend.HEADERS.headers.syntax.items.attributes import (
    ATTRIBUTE_SPECIFIER,
    STATIC_ASSERT_DECL,
)
from core.frontend.HEADERS.headers.syntax.items.declarators import GENERAL_DECLARATOR
from core.frontend.HEADERS.headers.syntax.items.expressions import CONST_EXPR
from core.frontend.HEADERS.headers.syntax.items.specifiers import DECL_SPECIFIERS


class BITFIELD_SPEC(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('COLON'),
        cmb.Ref(CONST_EXPR)
    )
    nodeable = True


class STRUCT_DECLARATOR(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Seq(
            cmb.Ref(GENERAL_DECLARATOR),
            cmb.Opt(cmb.Ref(BITFIELD_SPEC))
        ),
        cmb.Ref(BITFIELD_SPEC)
    )
    nodeable = True


class STRUCT_MEMBER(cmb.RuleItem):
    pass


class STRUCT_BODY(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=Token.LBRACE,
        close=Token.RBRACE,
        content=cmb.Many(cmb.Ref(STRUCT_MEMBER)),
        allow_empty=True
    )
    nodeable = True


class STRUCT_UNION_SPECIFIER(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Alt(
            cmb.MatchKeyword('struct'),
            cmb.MatchKeyword('union')
        ),
        cmb.Many(cmb.Ref(ATTRIBUTE_SPECIFIER)),
        cmb.Alt(
            cmb.Seq(
                cmb.Opt(cmb.MatchToken('IDENT')),
                cmb.Ref(STRUCT_BODY)
            ),
            cmb.Seq(
                cmb.MatchToken('IDENT'),
                cmb.Not(cmb.Peek(cmb.MatchToken('LBRACE')))
            )
        )
    )
    nodeable = True


STRUCT_MEMBER.entrypoint = cmb.Alt(
    cmb.Ref(STATIC_ASSERT_DECL),
    cmb.Seq(
        cmb.Ref(DECL_SPECIFIERS),
        cmb.Opt(
            cmb.Separator(
                sep=Token.COMMA,
                values=[cmb.Ref(STRUCT_DECLARATOR)],
                min=1
            )
        ),
        cmb.Many(cmb.Ref(ATTRIBUTE_SPECIFIER)),
        cmb.MatchToken('SEMICOLON')
    )
)
STRUCT_MEMBER.nodeable = True


__all__ = [
    'BITFIELD_SPEC',
    'STRUCT_BODY',
    'STRUCT_DECLARATOR',
    'STRUCT_MEMBER',
    'STRUCT_UNION_SPECIFIER',
]

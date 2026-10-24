from gram import combinators as cmb
from gram.core.lexer import Token

from core.frontend.HEADERS.headers.syntax.items.attributes import ATTRIBUTE_SPECIFIER
from core.frontend.HEADERS.headers.syntax.items.expressions import CONST_EXPR
from core.frontend.HEADERS.headers.syntax.items.specifiers import (
    ALIASED_TYPE_SPEC,
    BASIC_TYPE_SPEC,
    TAG_SPECIFIER,
)
from core.frontend.HEADERS.headers.syntax.items.struct_decl import STRUCT_UNION_SPECIFIER


class ENUMERATOR(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Many(cmb.Ref(ATTRIBUTE_SPECIFIER)),
        cmb.Opt(
            cmb.Seq(
                cmb.MatchToken('ASSIGN'),
                cmb.Ref(CONST_EXPR)
            )
        )
    )
    nodeable = True


class ENUM_BODY(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=Token.LBRACE,
        close=Token.RBRACE,
        content=cmb.Opt(
            cmb.Separator(
                sep=Token.COMMA,
                values=[cmb.Ref(ENUMERATOR)],
                min=1,
                allow_trailing=True
            )
        ),
        allow_empty=True
    )
    nodeable = True


class ENUM_UNDERLYING_TYPE(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(BASIC_TYPE_SPEC),
        cmb.Ref(ALIASED_TYPE_SPEC)
    )
    nodeable = True


class ENUM_SPECIFIER(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('enum'),
        cmb.Many(cmb.Ref(ATTRIBUTE_SPECIFIER)),
        cmb.Alt(
            cmb.Seq(
                cmb.Opt(cmb.MatchToken('IDENT')),
                cmb.Opt(
                    cmb.Seq(
                        cmb.MatchToken('COLON'),
                        cmb.Ref(ENUM_UNDERLYING_TYPE)
                    )
                ),
                cmb.Ref(ENUM_BODY)
            ),
            cmb.Seq(
                cmb.MatchToken('IDENT'),
                cmb.Opt(
                    cmb.Seq(
                        cmb.MatchToken('COLON'),
                        cmb.Ref(ENUM_UNDERLYING_TYPE)
                    )
                ),
                cmb.Not(cmb.Peek(cmb.MatchToken('LBRACE')))
            )
        )
    )
    nodeable = True


TAG_SPECIFIER.entrypoint = cmb.Alt(
    cmb.Ref(STRUCT_UNION_SPECIFIER),
    cmb.Ref(ENUM_SPECIFIER)
)
TAG_SPECIFIER.nodeable = True


class TAG_DECL(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Many(cmb.Ref(ATTRIBUTE_SPECIFIER)),
        cmb.Ref(TAG_SPECIFIER),
        cmb.Many(cmb.Ref(ATTRIBUTE_SPECIFIER)),
        cmb.MatchToken('SEMICOLON')
    )
    nodeable = True


__all__ = [
    'ENUMERATOR',
    'ENUM_BODY',
    'ENUM_SPECIFIER',
    'ENUM_UNDERLYING_TYPE',
    'TAG_DECL',
    'TAG_SPECIFIER',
]

from gram import combinators as cmb
from gram.core.lexer import Token

from core.frontend.HEADERS.headers.syntax.items.attributes import ATTRIBUTE_SPECIFIER
from core.frontend.HEADERS.headers.syntax.items.expressions import CONST_EXPR, TYPE_NAME
from core.frontend.HEADERS.headers.syntax.items.specifiers import (
    DECL_SPECIFIERS,
    FUNCTION_SPECIFIER,
    QUALIFIER,
)


class PARAMS(cmb.RuleItem):
    pass


class GENERAL_DECLARATOR(cmb.RuleItem):
    pass


class ABSTRACT_DECLARATOR(cmb.RuleItem):
    pass


class POINTER_MODIFIER(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(QUALIFIER),
        cmb.Ref(FUNCTION_SPECIFIER),
        cmb.Ref(ATTRIBUTE_SPECIFIER)
    )
    nodeable = True


class POINTER_PART(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Many(cmb.Ref(POINTER_MODIFIER)),
        cmb.MatchToken('STAR'),
        cmb.Many(cmb.Ref(POINTER_MODIFIER))
    )
    nodeable = True


class POINTER(cmb.RuleItem):
    entrypoint = cmb.Some(cmb.Ref(POINTER_PART))
    nodeable = True


class VLA_STAR(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Many(cmb.Ref(QUALIFIER)),
        cmb.MatchToken('STAR'),
        cmb.Peek(cmb.MatchToken('RBRACKET'))
    )
    nodeable = True


class ARRAY_DIMENSION(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=Token.LBRACKET,
        close=Token.RBRACKET,
        content=cmb.Opt(
            cmb.Alt(
                cmb.Ref(VLA_STAR),
                cmb.Seq(
                    cmb.Many(cmb.Alt(cmb.MatchKeyword('static'), cmb.Ref(QUALIFIER))),
                    cmb.Opt(cmb.Ref(CONST_EXPR))
                )
            )
        ),
        allow_empty=True
    )
    nodeable = True


class DECLARATOR_SUFFIX(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(ARRAY_DIMENSION),
        cmb.Ref(PARAMS)
    )
    nodeable = True


class DECLARATOR_MODIFIER(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(FUNCTION_SPECIFIER),
        cmb.Ref(ATTRIBUTE_SPECIFIER)
    )
    nodeable = True


GENERAL_DECLARATOR.entrypoint = cmb.Seq(
    cmb.Opt(cmb.Ref(POINTER)),
    cmb.Many(cmb.Ref(DECLARATOR_MODIFIER)),
    cmb.Alt(
        cmb.MatchToken('IDENT'),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Ref(GENERAL_DECLARATOR)
        )
    ),
    cmb.Many(cmb.Ref(DECLARATOR_SUFFIX)),
    cmb.Many(cmb.Ref(ATTRIBUTE_SPECIFIER))
)
GENERAL_DECLARATOR.nodeable = True


ABSTRACT_DECLARATOR.entrypoint = cmb.Alt(
    cmb.Seq(
        cmb.Opt(cmb.Ref(POINTER)),
        cmb.Many(cmb.Ref(DECLARATOR_MODIFIER)),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Ref(ABSTRACT_DECLARATOR)
        ),
        cmb.Many(cmb.Ref(DECLARATOR_SUFFIX))
    ),
    cmb.Seq(
        cmb.Opt(cmb.Ref(POINTER)),
        cmb.Some(cmb.Ref(DECLARATOR_SUFFIX))
    ),
    cmb.Ref(POINTER)
)
ABSTRACT_DECLARATOR.nodeable = True


class PARAM_DECLARATOR(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(GENERAL_DECLARATOR),
        cmb.Ref(ABSTRACT_DECLARATOR)
    )
    nodeable = True


class PARAM_STANDARD(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(DECL_SPECIFIERS),
        cmb.Opt(cmb.Ref(PARAM_DECLARATOR)),
        cmb.Many(cmb.Ref(ATTRIBUTE_SPECIFIER))
    )
    nodeable = True


class PARAM(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.MatchToken('THREE_DOTS'),
        cmb.Ref(PARAM_STANDARD),
        cmb.MatchKeyword('void')
    )
    nodeable = True


PARAMS.entrypoint = cmb.Enclosed(
    open=Token.LPAREN,
    close=Token.RPAREN,
    content=cmb.Opt(
        cmb.Separator(
            sep=Token.COMMA,
            values=[cmb.Ref(PARAM)],
            min=1
        )
    ),
    allow_empty=True
)
PARAMS.nodeable = True


TYPE_NAME.entrypoint = cmb.Seq(
    cmb.Ref(DECL_SPECIFIERS),
    cmb.Opt(cmb.Ref(ABSTRACT_DECLARATOR))
)
TYPE_NAME.nodeable = True


class TYPE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(DECL_SPECIFIERS),
        cmb.Opt(cmb.Ref(ABSTRACT_DECLARATOR))
    )
    nodeable = True


__all__ = [
    'ABSTRACT_DECLARATOR',
    'ARRAY_DIMENSION',
    'DECLARATOR_MODIFIER',
    'DECLARATOR_SUFFIX',
    'GENERAL_DECLARATOR',
    'PARAM',
    'PARAMS',
    'PARAM_DECLARATOR',
    'PARAM_STANDARD',
    'POINTER',
    'POINTER_MODIFIER',
    'POINTER_PART',
    'TYPE',
    'TYPE_NAME',
    'VLA_STAR',
]

from gram import combinators as cmb
from gram.core.lexer import Token

from core.frontend.HEADERS.headers.syntax.items.expressions import CONST_EXPR


class C23_ATTR_ARG(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('STRING'),
        cmb.MatchToken('NUMBER'),
        cmb.MatchToken('COMMA')
    )
    nodeable = False


class C23_ATTRIBUTE_ITEM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Opt(
            cmb.Seq(
                cmb.MatchToken('COLON'),
                cmb.MatchToken('COLON'),
                cmb.MatchToken('IDENT')
            )
        ),
        cmb.Opt(
            cmb.Enclosed(
                open=Token.LPAREN,
                close=Token.RPAREN,
                content=cmb.Some(cmb.Ref(C23_ATTR_ARG)),
                allow_empty=True
            )
        )
    )
    nodeable = True


class C23_ATTRIBUTE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('LBRACKET'),
        cmb.MatchToken('LBRACKET'),
        cmb.Separator(
            sep=Token.COMMA,
            values=[cmb.Ref(C23_ATTRIBUTE_ITEM)],
            min=1
        ),
        cmb.MatchToken('RBRACKET'),
        cmb.MatchToken('RBRACKET')
    )
    nodeable = True


class GNU_ATTR_ARG(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('KEYWORD'),
        cmb.MatchToken('STRING'),
        cmb.MatchToken('NUMBER'),
        cmb.MatchToken('COMMA'),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Some(
                cmb.Alt(
                    cmb.MatchToken('IDENT'),
                    cmb.MatchToken('KEYWORD'),
                    cmb.MatchToken('NUMBER'),
                    cmb.MatchToken('STRING'),
                    cmb.MatchToken('COMMA')
                )
            ),
            allow_empty=True
        )
    )
    nodeable = False


class GNU_ATTRIBUTE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Alt(
            cmb.MatchKeyword('__attribute__'),
            cmb.MatchKeyword('__attribute')
        ),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Enclosed(
                open=Token.LPAREN,
                close=Token.RPAREN,
                content=cmb.Some(cmb.Ref(GNU_ATTR_ARG)),
                allow_empty=True
            )
        )
    )
    nodeable = True


class DECLSPEC_ATTRIBUTE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('__declspec'),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Some(
                cmb.Alt(
                    cmb.MatchToken('IDENT'),
                    cmb.MatchToken('NUMBER'),
                    cmb.MatchToken('STRING'),
                    cmb.Enclosed(
                        open=Token.LPAREN,
                        close=Token.RPAREN,
                        content=cmb.Some(
                            cmb.Alt(
                                cmb.MatchToken('IDENT'),
                                cmb.MatchToken('NUMBER')
                            )
                        ),
                        allow_empty=True
                    )
                )
            )
        )
    )
    nodeable = True


class EXTENSION_SPECIFIER(cmb.RuleItem):
    entrypoint = cmb.MatchKeyword('__extension__')
    nodeable = True


class ASM_SPECIFIER(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Alt(
            cmb.MatchKeyword('__asm__'),
            cmb.MatchKeyword('__asm'),
            cmb.MatchKeyword('asm')
        ),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Some(cmb.MatchToken('STRING'))
        )
    )
    nodeable = True


class ATTRIBUTE_SPECIFIER(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(C23_ATTRIBUTE),
        cmb.Ref(GNU_ATTRIBUTE),
        cmb.Ref(DECLSPEC_ATTRIBUTE),
        cmb.Ref(EXTENSION_SPECIFIER),
        cmb.Ref(ASM_SPECIFIER)
    )
    nodeable = True


class STATIC_ASSERT_DECL(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Alt(
            cmb.MatchKeyword('_Static_assert'),
            cmb.MatchKeyword('static_assert')
        ),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Seq(
                cmb.Ref(CONST_EXPR),
                cmb.Opt(
                    cmb.Seq(
                        cmb.MatchToken('COMMA'),
                        cmb.Some(cmb.MatchToken('STRING'))
                    )
                )
            )
        ),
        cmb.MatchToken('SEMICOLON')
    )
    nodeable = True


__all__ = [
    'ASM_SPECIFIER',
    'ATTRIBUTE_SPECIFIER',
    'C23_ATTRIBUTE',
    'C23_ATTRIBUTE_ITEM',
    'C23_ATTR_ARG',
    'DECLSPEC_ATTRIBUTE',
    'EXTENSION_SPECIFIER',
    'GNU_ATTRIBUTE',
    'GNU_ATTR_ARG',
    'STATIC_ASSERT_DECL',
]

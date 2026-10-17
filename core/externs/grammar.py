from gram import combinators as cmb
from gram import lexer

from core.initiator.rules.value import ALIAS, PAIR_DECLARE_PARAM, PAIR_PARAM, SEGMENT_TYPE, VALUE


class EXTERN_TYPE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(
            cmb.MatchKeyword('ptr'),
        ),

        cmb.Alt(
            cmb.Ref(SEGMENT_TYPE),
            cmb.MatchToken('IDENT'),
        ),
        cmb.Opt(cmb.MatchToken(lexer.Token.STAR)),
    )
    nodeable = True


class EXTERN_PARAM_NAME(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.MatchToken('IDENT'),
        cmb.MatchKeyword('flags'),
    )
    nodeable = True


class EXTERN_PARAM(cmb.RuleItem):
    entrypoint = cmb.Alt(
        # C-style: type [*] name [= value]
        cmb.Seq(
            cmb.Ref(EXTERN_TYPE),
            cmb.Opt(cmb.MatchToken(lexer.Token.STAR)),
            cmb.Ref(EXTERN_PARAM_NAME),
            cmb.Opt(
                cmb.Seq(
                    cmb.MatchToken(lexer.Token.ASSIGN),
                    cmb.Ref(VALUE),
                )
            ),
        ),
        # Easy-C style: name: type [= value]
        cmb.Ref(PAIR_DECLARE_PARAM),
        cmb.Ref(PAIR_PARAM),
        # Star-ident: *name [= value]
        cmb.Seq(
            cmb.MatchToken(lexer.Token.STAR),
            cmb.Ref(EXTERN_PARAM_NAME),
            cmb.Opt(
                cmb.Seq(
                    cmb.MatchToken(lexer.Token.ASSIGN),
                    cmb.Ref(VALUE),
                )
            ),
        ),
        # Anonymous type (like `void` in `(void)`)
        cmb.Ref(EXTERN_TYPE),
    )
    nodeable = True


class EXTERN_PARAMS(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.Opt(
            cmb.Separator(
                sep=lexer.Token.COMMA,
                values=[cmb.Ref(EXTERN_PARAM)],
            ),
        ),
    )
    nodeable = True


class EXTERN_FUNC(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(EXTERN_TYPE),
        cmb.Opt(cmb.MatchToken(lexer.Token.STAR)),
        cmb.MatchToken('IDENT'),
        cmb.Ref(EXTERN_PARAMS),
        cmb.Opt(cmb.Ref(ALIAS)),
    )
    nodeable = True


class EXTERN_ENTRYPOINT(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(EXTERN_FUNC),
    )


extern_grammar = EXTERN_ENTRYPOINT

__all__ = [
    'EXTERN_TYPE',
    'EXTERN_PARAM_NAME',
    'EXTERN_PARAM',
    'EXTERN_PARAMS',
    'EXTERN_FUNC',
    'EXTERN_ENTRYPOINT',
    'extern_grammar',
]

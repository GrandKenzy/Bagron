from gram import combinators as cmb
from gram import lexer

from core.frontend.C.syntax.items.value import POINTER, QUALIFIER, TYPE


class STRUCT_FIELD(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.Ref(QUALIFIER)),
        cmb.Ref(TYPE),
        cmb.Opt(cmb.Ref(POINTER)),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('SEMICOLON'),
    )


class STRUCT_BODY(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LBRACE,
        close=lexer.Token.RBRACE,
        content=cmb.Some(cmb.Ref(STRUCT_FIELD)),
        allow_empty=True,
        skip_whitespace=True
    )


class STRUCT(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('struct'),
        cmb.MatchToken('IDENT'),
        cmb.Opt(cmb.Ref(STRUCT_BODY)),
        cmb.MatchToken('SEMICOLON'),
    )


class UNION(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('union'),
        cmb.MatchToken('IDENT'),
        cmb.Opt(cmb.Ref(STRUCT_BODY)),
        cmb.MatchToken('SEMICOLON'),
    )


__all__ = [
    'STRUCT',
    'STRUCT_BODY',
    'STRUCT_FIELD',
    'UNION',
]

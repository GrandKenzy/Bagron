from gram import combinators as cmb
from gram import lexer


class ENUM_ITEM(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Opt(
            cmb.Seq(
                cmb.MatchToken('ASSIGN'),
                cmb.Alt(
                    cmb.MatchToken('NUMBER'),
                    cmb.MatchToken('IDENT')
                )
            )
        )
    )


class ENUM_BODY(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LBRACE,
        close=lexer.Token.RBRACE,
        content=cmb.Separator(
            sep=lexer.Token.COMMA,
            values=[cmb.Ref(ENUM_ITEM)],
            allow_trailing=True,
        ),
        allow_empty=True,
        skip_whitespace=True
    )


class ENUM(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('enum'),
        cmb.MatchToken('IDENT'),
        cmb.Opt(cmb.Ref(ENUM_BODY)),
        cmb.MatchToken('SEMICOLON'),
    )


__all__ = [
    'ENUM',
    'ENUM_BODY',
    'ENUM_ITEM',
]

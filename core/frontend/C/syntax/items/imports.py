from gram import combinators as cmb
from gram import lexer


class INCLUDE_HEADER(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Alt(
        cmb.MatchToken('STRING'),
        cmb.Enclosed(
            open=lexer.Token.LESS,
            close=lexer.Token.GREATER,
            content=cmb.Some(
                cmb.Alt(
                    cmb.MatchToken('IDENT'),
                    cmb.MatchToken('DOT'),
                    cmb.MatchToken('SLASH'),
                )
            ),
            allow_empty=False
        )
    )


class INCLUDE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchToken('HASH')),
        cmb.MatchKeyword('include'),
        cmb.Ref(INCLUDE_HEADER)
    )


class PRAGMA(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchToken('HASH')),
        cmb.MatchKeyword('pragma'),
        cmb.Some(
            cmb.Alt(
                cmb.MatchToken('IDENT'),
                cmb.MatchToken('STRING'),
                cmb.MatchToken('NUMBER')
            )
        )
    )


__all__ = [
    'INCLUDE',
    'INCLUDE_HEADER',
    'PRAGMA',
]

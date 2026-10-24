from gram import combinators as cmb
from gram import lexer

from core.frontend.C.syntax.items.call import CALL_STMT
from core.frontend.C.syntax.items.value import RETURN, VALUE
from core.frontend.C.syntax.items.var_decl import (
    VAR,
    VAR_ASSIGNATION,
    VAR_ASSIGNATION_NO_SEMI,
    VAR_INLINE,
)


class WHILE(cmb.RuleItem):
    nodeable = True


class DO_WHILE(cmb.RuleItem):
    nodeable = True


class FOR(cmb.RuleItem):
    nodeable = True


class IF(cmb.RuleItem):
    nodeable = True


class ELSE_IF(cmb.RuleItem):
    nodeable = True


class ELSE(cmb.RuleItem):
    nodeable = True


class BREAK(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('break'),
        cmb.MatchToken('SEMICOLON')
    )


class CONTINUE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('continue'),
        cmb.MatchToken('SEMICOLON')
    )


class CONDITION(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.Ref(VALUE)
    )


class FOR_HEADER(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.Seq(
            cmb.Opt(
                cmb.Alt(
                    cmb.Ref(VAR_INLINE),
                    cmb.Ref(VAR_ASSIGNATION_NO_SEMI),
                    cmb.Ref(VALUE),
                )
            ),
            cmb.MatchToken('SEMICOLON'),
            cmb.Opt(cmb.Ref(VALUE)),
            cmb.MatchToken('SEMICOLON'),
            cmb.Opt(
                cmb.Alt(
                    cmb.Ref(VAR_ASSIGNATION_NO_SEMI),
                    cmb.Ref(VALUE),
                )
            ),
        )
    )


class STATEMENT(cmb.RuleItem):
    nodeable = True


class STATEMENT_BLOCK(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LBRACE,
        close=lexer.Token.RBRACE,
        content=cmb.Some(cmb.Ref(STATEMENT)),
        allow_empty=True,
        skip_whitespace=True
    )


STATEMENT.entrypoint = cmb.Alt(
    cmb.Ref(VAR),
    cmb.Ref(VAR_ASSIGNATION),
    cmb.Ref(CALL_STMT),
    cmb.Ref(RETURN),
    cmb.Ref(IF),
    cmb.Ref(WHILE),
    cmb.Ref(DO_WHILE),
    cmb.Ref(FOR),
    cmb.Ref(BREAK),
    cmb.Ref(CONTINUE),
    cmb.Ref(STATEMENT_BLOCK),
)


WHILE.entrypoint = cmb.Seq(
    cmb.MatchKeyword('while'),
    cmb.Ref(CONDITION),
    cmb.Alt(
        cmb.Ref(STATEMENT_BLOCK),
        cmb.Ref(STATEMENT)
    )
)


DO_WHILE.entrypoint = cmb.Seq(
    cmb.MatchKeyword('do'),
    cmb.Alt(
        cmb.Ref(STATEMENT_BLOCK),
        cmb.Ref(STATEMENT)
    ),
    cmb.MatchKeyword('while'),
    cmb.Ref(CONDITION),
    cmb.MatchToken('SEMICOLON')
)


FOR.entrypoint = cmb.Seq(
    cmb.MatchKeyword('for'),
    cmb.Ref(FOR_HEADER),
    cmb.Alt(
        cmb.Ref(STATEMENT_BLOCK),
        cmb.Ref(STATEMENT)
    )
)


ELSE_IF.entrypoint = cmb.Seq(
    cmb.MatchKeyword('else'),
    cmb.MatchKeyword('if'),
    cmb.Ref(CONDITION),
    cmb.Alt(
        cmb.Ref(STATEMENT_BLOCK),
        cmb.Ref(STATEMENT)
    )
)


ELSE.entrypoint = cmb.Seq(
    cmb.MatchKeyword('else'),
    cmb.Alt(
        cmb.Ref(STATEMENT_BLOCK),
        cmb.Ref(STATEMENT)
    )
)


IF.entrypoint = cmb.Seq(
    cmb.MatchKeyword('if'),
    cmb.Ref(CONDITION),
    cmb.Alt(
        cmb.Ref(STATEMENT_BLOCK),
        cmb.Ref(STATEMENT)
    ),
    cmb.Many(cmb.Ref(ELSE_IF)),
    cmb.Opt(cmb.Ref(ELSE))
)


__all__ = [
    'BREAK',
    'CONDITION',
    'CONTINUE',
    'DO_WHILE',
    'ELSE',
    'ELSE_IF',
    'FOR',
    'FOR_HEADER',
    'IF',
    'STATEMENT',
    'STATEMENT_BLOCK',
    'WHILE',
]

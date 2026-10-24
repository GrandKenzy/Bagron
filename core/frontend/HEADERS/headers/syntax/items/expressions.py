from gram import combinators as cmb
from gram.core.lexer import Token


class CONST_EXPR(cmb.RuleItem):
    pass


class TYPE_NAME(cmb.RuleItem):
    pass


class EXPR_UNARY_OP(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.MatchToken('PLUS'),
        cmb.MatchToken('MINUS'),
        cmb.MatchToken('NOT'),
        cmb.MatchToken('NOT_LOGIC'),
        cmb.MatchToken('STAR'),
        cmb.MatchToken('AND')
    )
    nodeable = True


class EXPR_BIN_OP(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.MatchToken('PLUS'),
        cmb.MatchToken('MINUS'),
        cmb.MatchToken('STAR'),
        cmb.MatchToken('SLASH'),
        cmb.MatchToken('PERCENT'),
        cmb.MatchToken('SHL'),
        cmb.MatchToken('SHR'),
        cmb.MatchToken('AND'),
        cmb.MatchToken('OR'),
        cmb.MatchToken('XOR'),
        cmb.MatchToken('AND_LOGIC'),
        cmb.MatchToken('OR_LOGIC'),
        cmb.MatchToken('EQUAL'),
        cmb.MatchToken('NOT_EQUAL'),
        cmb.MatchToken('LESS'),
        cmb.MatchToken('GREATER'),
        cmb.MatchToken('LESS_EQUAL'),
        cmb.MatchToken('GREATER_EQUAL'),
        cmb.MatchToken('QUESTION'),
        cmb.MatchToken('COLON')
    )
    nodeable = True


class SIZEOF_ALIGNOF_EXPR(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Alt(
            cmb.MatchKeyword('sizeof'),
            cmb.MatchKeyword('alignof'),
            cmb.MatchKeyword('_Alignof')
        ),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Alt(
                cmb.Ref(TYPE_NAME),
                cmb.Ref(CONST_EXPR)
            )
        )
    )
    nodeable = True


class EXPR_POSTFIX(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Seq(
            cmb.MatchToken('DOT'),
            cmb.MatchToken('IDENT')
        ),
        cmb.Seq(
            cmb.MatchToken('ARROW'),
            cmb.MatchToken('IDENT')
        ),
        cmb.Enclosed(
            open=Token.LBRACKET,
            close=Token.RBRACKET,
            content=cmb.Ref(CONST_EXPR)
        ),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Opt(
                cmb.Separator(
                    sep=Token.COMMA,
                    values=[cmb.Ref(CONST_EXPR)],
                    min=1
                )
            ),
            allow_empty=True
        )
    )
    nodeable = True


class EXPR_ATOM(cmb.RuleItem):
    pass


class TYPE_CAST_EXPR(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Ref(TYPE_NAME)
        ),
        cmb.Ref(EXPR_ATOM)
    )
    nodeable = True


class NUMBER_LITERAL(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('NUMBER'),
        cmb.Opt(cmb.MatchToken('IDENT'))
    )
    nodeable = True


EXPR_ATOM.entrypoint = cmb.Seq(
    cmb.Many(cmb.Ref(EXPR_UNARY_OP)),
    cmb.Alt(
        cmb.Ref(SIZEOF_ALIGNOF_EXPR),
        cmb.Ref(TYPE_CAST_EXPR),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Ref(CONST_EXPR)
        ),
        cmb.Ref(NUMBER_LITERAL),
        cmb.MatchToken('CHAR'),
        cmb.Some(cmb.MatchToken('STRING')),
        cmb.MatchKeyword('NULL'),
        cmb.MatchKeyword('nullptr'),
        cmb.MatchKeyword('true'),
        cmb.MatchKeyword('false'),
        cmb.MatchToken('IDENT')
    ),
    cmb.Many(cmb.Ref(EXPR_POSTFIX))
)
EXPR_ATOM.nodeable = True


CONST_EXPR.entrypoint = cmb.Seq(
    cmb.Ref(EXPR_ATOM),
    cmb.Many(
        cmb.Seq(
            cmb.Ref(EXPR_BIN_OP),
            cmb.Ref(EXPR_ATOM)
        )
    )
)
CONST_EXPR.nodeable = True


__all__ = [
    'CONST_EXPR',
    'EXPR_ATOM',
    'EXPR_BIN_OP',
    'EXPR_POSTFIX',
    'EXPR_UNARY_OP',
    'NUMBER_LITERAL',
    'SIZEOF_ALIGNOF_EXPR',
    'TYPE_CAST_EXPR',
    'TYPE_NAME',
]

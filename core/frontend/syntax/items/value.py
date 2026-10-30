from gram import combinators as cmb
from gram import lexer


class _SAME_LINE(cmb.Combinator):
    """Run a postfix suffix only when it starts on the current source line."""

    def __init__(self, combinator: cmb.Combinator):
        super().__init__()
        self.combinator = combinator

    def parse(self, analyzer):
        parser = analyzer.parser
        current = parser.peek() if not parser.empty() else None
        previous = (
            parser.tokens[parser.pos - 1]
            if parser.pos > 0
            else None
        )
        if (
            current is None
            or previous is None
            or current.line != previous.line
        ):
            return None
        return analyzer.visitor(self.combinator)


class VALUE(cmb.RuleItem):
    nodeable = True


class _OPTIONAL_ARRAY_DIMENSION(cmb.Combinator):
    """Parse a dimension only when the suffix is not ``[]``.

    ``Opt(Ref(VALUE))`` cannot be used here because the expression parser
    stages a deep failure when its first token is ``]``.  A small lookahead
    keeps the long-standing inferred-array syntax intact while still allowing
    dimensions such as ``[8 * 100]``.
    """

    def parse(self, analyzer):
        parser = analyzer.parser
        token = parser.peek() if not parser.empty() else None
        if getattr(getattr(token, 'token', None), 'name', None) == 'RBRACKET':
            return []
        return analyzer.visitor(cmb.Ref(VALUE))


class ARRAY_SUFFIX(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('LBRACKET'),
        # Fixed dimensions may be constant arithmetic expressions.  Keeping
        # the expression in the AST lets the semantic pass distinguish a
        # compile-time capacity from an inferred dimension.
        _OPTIONAL_ARRAY_DIMENSION(),
        cmb.MatchToken('RBRACKET'),
    )
    nodeable = False


class BITINT_TYPE(cmb.RuleItem):
    """Fixed-width integer type using Bagron's angle-bracket syntax."""
    entrypoint = cmb.Seq(
        cmb.Alt(
            cmb.MatchKeyword('Bint'),
            cmb.MatchKeyword('uBint'),
        ),
        cmb.MatchToken('LESS'),
        cmb.MatchToken('NUMBER'),
        cmb.MatchToken('GREATER'),
    )
    nodeable = True


class TYPE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchKeyword('const')),
        cmb.Opt(cmb.MatchKeyword('unique')),
        cmb.Alt(
            cmb.Ref(BITINT_TYPE),
            cmb.MatchGroup('types'),
            cmb.MatchToken('IDENT'),
        ),
        cmb.Many(cmb.Ref(ARRAY_SUFFIX)),
    )
    nodeable = False


class POINTER(cmb.RuleItem):
    entrypoint = cmb.Some(cmb.MatchToken('STAR'))
    nodeable = True


class DECLARATOR(cmb.RuleItem):
    """Declarator with an optional const pointer qualifier."""
    entrypoint = cmb.Alt(
        cmb.Seq(
            cmb.MatchKeyword('const'),
            cmb.MatchToken('IDENT'),
            cmb.Ref(POINTER),
        ),
        cmb.Seq(
            cmb.MatchToken('IDENT'),
            cmb.Opt(cmb.Ref(POINTER)),
        ),
    )
    nodeable = True


class ALIAS(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('as'),
        cmb.MatchToken('IDENT'),
    )
    nodeable = True


class PAIR_PARAM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(DECLARATOR),
        cmb.MatchToken('COLON'),
        cmb.Ref(TYPE),
        cmb.Opt(
            cmb.Seq(
                cmb.MatchToken('ASSIGN'),
                cmb.Ref(VALUE),
            )
        ),
    )
    nodeable = True


class PARAMETERS(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.Separator(
            sep=lexer.Token.COMMA,
            values=[cmb.Ref(PAIR_PARAM)],
        ),
    )
    nodeable = True


class ARGUMENTS(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.Separator(
            sep=lexer.Token.COMMA,
            values=cmb.Ref(VALUE),
        ),
        allow_empty=True,
        skip_whitespace=True,
    )
    nodeable = True


class ARRAY_VALUE(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LBRACE,
        close=lexer.Token.RBRACE,
        content=cmb.Separator(
            sep=lexer.Token.COMMA,
            values=cmb.Ref(VALUE),
            min=1,
            allow_trailing=True,
        ),
        allow_empty=True,
        skip_whitespace=True,
    )
    nodeable = True


class PAREN_VALUE(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.Ref(VALUE),
        skip_whitespace=True,
    )
    nodeable = True


class DEREF_TARGET(cmb.RuleItem):
    nodeable = True


DEREF_TARGET.entrypoint = cmb.Enclosed(
    open=lexer.Token.LPAREN,
    close=lexer.Token.RPAREN,
    content=cmb.Alt(
        cmb.MatchToken('IDENT'),
        cmb.Ref(DEREF_TARGET),
    ),
    skip_whitespace=True,
    allow_empty=False,
)


class MEMBER_ACCESS(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('DOT'),
        cmb.MatchToken('IDENT'),
    )
    nodeable = True


class DEREF_ASSIGN_TARGET(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.MatchToken('IDENT'),
        skip_whitespace=True,
        allow_empty=False,
    )
    nodeable = True


class INDEX_ACCESS(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LBRACKET,
        close=lexer.Token.RBRACKET,
        content=cmb.Ref(VALUE),
        skip_whitespace=True,
        allow_empty=False,
    )
    nodeable = True


class CALL_SUFFIX(cmb.RuleItem):
    entrypoint = cmb.Ref(ARGUMENTS)
    nodeable = True


class PRIMARY(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(PAREN_VALUE),
        cmb.Ref(ARRAY_VALUE),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('BOOL'),
        cmb.MatchToken('NULL'),
        cmb.MatchToken('STRING'),
        cmb.MatchToken('NUMBER'),
        cmb.MatchToken('DECIMAL'),
    )
    nodeable = True


class POSTFIX_EXPR(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(PRIMARY),
        cmb.Many(
            cmb.Alt(
                _SAME_LINE(cmb.Ref(CALL_SUFFIX)),
                _SAME_LINE(cmb.Ref(MEMBER_ACCESS)),
                _SAME_LINE(cmb.Ref(INDEX_ACCESS)),
            )
        ),
    )
    nodeable = True


class LOGICAL_NOT(cmb.RuleItem):
    """Word-form logical negation for the Bagron `not` keyword."""

    nodeable = True


LOGICAL_NOT.entrypoint = cmb.Seq(
    cmb.MatchKeyword('not'),
    cmb.Alt(
        cmb.Ref(LOGICAL_NOT),
        cmb.Ref(POSTFIX_EXPR),
    ),
)


class RETURN(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('return'),
        cmb.Opt(cmb.Ref(VALUE)),
    )
    nodeable = True


class RETURN_ASM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('return'),
        cmb.MatchKeyword('asm'),
    )
    nodeable = True


__all__ = [
    'ALIAS',
    'ARGUMENTS',
    'ARRAY_SUFFIX',
    'ARRAY_VALUE',
    'BITINT_TYPE',
    'CALL_SUFFIX',
    'DECLARATOR',
    'DEREF_ASSIGN_TARGET',
    'DEREF_TARGET',
    'INDEX_ACCESS',
    'LOGICAL_NOT',
    'MEMBER_ACCESS',
    'PARAMETERS',
    'PAIR_PARAM',
    'PAREN_VALUE',
    'POINTER',
    'POSTFIX_EXPR',
    'PRIMARY',
    'RETURN',
    'RETURN_ASM',
    'TYPE',
    'VALUE',
]

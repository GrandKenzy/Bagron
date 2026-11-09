from gram import combinators as cmb
from gram import lexer


class VALUE(cmb.RuleItem):
    nodeable = True


class ARRAY_SUFFIX(cmb.RuleItem):
    # Keep the delimiters in the AST: Bagron's semantic pass uses them to
    # distinguish inferred `[]` from fixed `[8 * 100]` dimensions. Ordered
    # `Alt` rollback provides the optional-content behavior without a custom
    # lookahead combinator and remains closed under Gram AOT compilation.
    entrypoint = cmb.Alt(
        cmb.Seq(
            cmb.MatchToken('LBRACKET'),
            cmb.MatchToken('RBRACKET'),
        ),
        cmb.Seq(
            cmb.MatchToken('LBRACKET'),
            cmb.Ref(VALUE),
            cmb.MatchToken('RBRACKET'),
        ),
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


class QUALIFIED_TYPE(cmb.RuleItem):
    """A type exported through a module or library namespace."""

    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Some(
            cmb.Seq(
                cmb.MatchToken('DOT'),
                cmb.MatchToken('IDENT'),
            )
        ),
    )
    nodeable = False


class TYPE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchKeyword('const')),
        cmb.Opt(cmb.MatchKeyword('unique')),
        cmb.Alt(
            cmb.Ref(BITINT_TYPE),
            cmb.MatchGroup('types'),
            cmb.Ref(QUALIFIED_TYPE),
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


class DESIGNATED_FIELD(cmb.RuleItem):
    """One explicitly named member in an aggregate literal."""

    entrypoint = cmb.Seq(
        cmb.MatchToken('DOT'),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('ASSIGN'),
        cmb.Ref(VALUE),
    )
    nodeable = True


class AGGREGATE_VALUE(cmb.RuleItem):
    """A nominal aggregate value such as ``Point{ .x = 1 }``."""

    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Enclosed(
            open=lexer.Token.LBRACE,
            close=lexer.Token.RBRACE,
            content=cmb.Separator(
                sep=lexer.Token.COMMA,
                values=cmb.Ref(DESIGNATED_FIELD),
                min=1,
                allow_trailing=True,
            ),
            allow_empty=True,
            skip_whitespace=True,
        ),
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


class CAST_SUFFIX(cmb.RuleItem):
    """Explicit scalar conversion suffix, for example ``raw as uint8``."""

    entrypoint = cmb.Seq(
        cmb.MatchKeyword('as'),
        cmb.Ref(TYPE),
    )
    nodeable = True


class CALL_SUFFIX(cmb.RuleItem):
    entrypoint = cmb.Ref(ARGUMENTS)
    nodeable = True


class PRIMARY(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(PAREN_VALUE),
        cmb.Ref(AGGREGATE_VALUE),
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
                cmb.SameLine(cmb.Ref(CALL_SUFFIX)),
                cmb.SameLine(cmb.Ref(MEMBER_ACCESS)),
                cmb.SameLine(cmb.Ref(INDEX_ACCESS)),
                cmb.SameLine(cmb.Ref(CAST_SUFFIX)),
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
    'AGGREGATE_VALUE',
    'ARGUMENTS',
    'ARRAY_SUFFIX',
    'ARRAY_VALUE',
    'BITINT_TYPE',
    'CAST_SUFFIX',
    'CALL_SUFFIX',
    'DECLARATOR',
    'DESIGNATED_FIELD',
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
    'QUALIFIED_TYPE',
    'RETURN',
    'RETURN_ASM',
    'TYPE',
    'VALUE',
]

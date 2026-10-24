from gram import combinators as cmb
from gram import lexer


class VALUE(cmb.RuleItem):
    """Regla base para expresions y valores evals a C."""
    nodeable = True


class LONG_LONG(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('long'),
        cmb.MatchKeyword('long')
    )
    nodeable = True


class SIGNED(cmb.RuleItem):
    entrypoint = cmb.MatchGroup('signed_')
    nodeable = False


class POINTER(cmb.RuleItem):
    """Maneja uno o más asteriscos para punteros simples y multis (ej: *, **, ***)."""
    entrypoint = cmb.Some(cmb.MatchToken('STAR'))
    nodeable = True


class QUALIFIER(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.MatchKeyword('volatile'),
        cmb.MatchKeyword('const'),
        cmb.MatchKeyword('restrict'),
        cmb.MatchKeyword('_Atomic'),
    )


class INTRINSIC_TYPE(cmb.RuleItem):
    """Maneja modificadores de tipo compuestos (signed, unsigned, long, short, int, etc.)."""
    entrypoint = cmb.Some(
        cmb.Alt(
            cmb.MatchGroup('types'),
            cmb.Ref(SIGNED),
            cmb.Ref(LONG_LONG),
            cmb.Ref(QUALIFIER)
        )
    )
    nodeable = True


class ALIASED_TYPE(cmb.RuleItem):
    entrypoint = cmb.Some(
        cmb.Seq(
            cmb.Opt(cmb.Some(cmb.Ref(QUALIFIER))),
            cmb.MatchToken('IDENT'),
            cmb.Opt(cmb.Some(cmb.Ref(QUALIFIER)))
        )
    )
    nodeable = True


class TYPE(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(INTRINSIC_TYPE),
        cmb.Ref(ALIASED_TYPE)
    )
    nodeable = False


class PAIR_PARAM(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Seq(
            cmb.Ref(TYPE),
            cmb.Opt(cmb.Ref(POINTER)),
            cmb.Opt(cmb.MatchToken('IDENT')),
        ),
        cmb.MatchToken('THREE_DOTS'),
    )
    nodeable = True


class PARAMETERS(cmb.RuleItem):
    """agrupador de parametros formales entre parentesis: int a, char* b o void."""
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.Alt(
            cmb.Separator(
                sep=lexer.Token.COMMA,
                values=[cmb.Ref(PAIR_PARAM)],
            ),
            cmb.MatchKeyword('void'),
        ),
        allow_empty=True,
        skip_whitespace=True
    )
    nodeable = True


class ARGUMENTS(cmb.RuleItem):
    """agrupador de argumentos para llamadas a funcin: (a, b + 1, "test")."""
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.Separator(
            sep=lexer.Token.COMMA,
            values=[cmb.Ref(VALUE)],
        ),
        allow_empty=True,
        skip_whitespace=True
    )
    nodeable = True


class RETURN(cmb.RuleItem):
    """sentencia de retorno"""
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('return'),
        cmb.Opt(cmb.Ref(VALUE)),
        cmb.MatchToken('SEMICOLON'),
    )
    nodeable = True


__all__ = [
    'ARGUMENTS',
    'PAIR_PARAM',
    'PARAMETERS',
    'POINTER',
    'QUALIFIER',
    'RETURN',
    'TYPE',
    'VALUE',
]
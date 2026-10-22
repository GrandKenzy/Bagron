from gram import combinators as cmb
from gram import lexer


class VALUE(cmb.RuleItem):
    """Valor vacío o genérico requerido para valores por defecto en parámetros."""
    entrypoint = cmb.Alt()
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
    """Maneja uno o más asteriscos para los punteros (ej: *, **, ***)."""
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
    """Maneja modificadores de tipo compuestos (signed, unsigned, long, short)."""
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
    """Parámetro individual estructurado (ej: identificador : tipo opcional con valor por defecto)."""
    entrypoint = cmb.Seq(
        cmb.Ref(TYPE)
        ,cmb.Opt(cmb.Ref(POINTER))
        ,cmb.MatchToken('IDENT')
    )
    nodeable = True


class PARAMETERS(cmb.RuleItem):
    """Agrupador de múltiples parámetros separados por comas entre paréntesis."""
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.Alt(
                cmb.Separator(
                sep=lexer.Token.COMMA,
                values=[cmb.Ref(PAIR_PARAM)],
                )
                ,cmb.MatchKeyword('void'),
            ),
        allow_empty=True,
        skip_whitespace=True
    )
    nodeable = True


__all__ = [
    'PAIR_PARAM',
    'PARAMETERS',
    'POINTER',
    'TYPE',
    'VALUE',
]
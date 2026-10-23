from gram import combinators as cmb
from gram import lexer


# Casos Especiales
class LONG_LONG_TOKEN(cmb.RuleItem):entrypoint = cmb.Tokenize(cmb.MatchKeyword('long'), cmb.MatchKeyword('long'), token_name='long long'); nodeable = True
class SIGNED(cmb.RuleItem): entrypoint = cmb.Alt(cmb.MatchGroup('signed_')); nodeable = True
class ELSEIF_TOKEN(cmb.RuleItem): entrypoint = cmb.Tokenize(cmb.MatchKeyword('else'), cmb.MatchKeyword('if'), token_name='else if')

class NO_RETURN_ATTR(cmb.RuleItem): 
    entrypoint = cmb.Tokenize(
        cmb.MatchToken('LBRACKET'),
        cmb.MatchToken('LBRACKET'),
        cmb.Literal('noreturn'),
        cmb.MatchToken('RBRACKET'),
        cmb.MatchToken('RBRACKET'),
    )
    nodeable = False

class ATOMIC_SPECIFIER(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('_Atomic'),
        cmb.Enclosed(
            open=lexer.tokens.Token.LPAREN,
            close=lexer.tokens.Token.RPAREN,
            content=cmb.MatchGroup('types')
        )
    )    
    nodeable = True

class BIT_INT(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('_BitInt'),
        cmb.Enclosed(
            open=lexer.tokens.Token.LPAREN,
            close=lexer.tokens.Token.RPAREN,
            content=cmb.Seq(
                cmb.Opt(cmb.Ref(SIGNED)),
                cmb.MatchToken('NUMBER')
            )
        )
    )     
    nodeable = True

# Conjuntos
class TYPES(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(LONG_LONG_TOKEN),
        cmb.Ref(SIGNED),
        cmb.Ref(BIT_INT),
        cmb.MatchGroup('types', values=['_BigInt'], behavior_values='deny')
    )
    nodeable = True
    
class QUALIFIER(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(ATOMIC_SPECIFIER),
        cmb.MatchGroup('qualifiers'),
    )
    nodeable = True
    
class TYPE(cmb.RuleItem):
    entrypoint = cmb.Some(cmb.Alt(
        cmb.Ref(QUALIFIER),
        cmb.Ref(TYPES),
    ))
    nodeable = True
from gram import combinators as cmb
from gram import lexer


class VALUE(cmb.RuleItem):
    nodeable = True


class ARRAY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('array'),
        cmb.MatchToken('LBRACKET'),
        cmb.Alt(
            cmb.MatchGroup('types'),
            cmb.MatchToken('IDENT'),
        ),
        cmb.MatchToken('COMMA'),
        cmb.Ref(VALUE),
        cmb.MatchToken('RBRACKET'),
    )
    nodeable = True

    
class TYPE(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(ARRAY),
        cmb.MatchGroup('types'),
        cmb.MatchToken('IDENT'),
    )
    nodeable = False


class POINTER(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Some(cmb.MatchToken('STAR')),
        cmb.MatchToken('IDENT')
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
        cmb.Opt(
            cmb.MatchKeyword('const')
        ),
        cmb.Ref(POINTER),
        cmb.MatchToken('COLON'),
        cmb.Ref(TYPE),
    )
    nodeable = True


class PAIR_DECLARE_PARAM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(PAIR_PARAM),
        cmb.MatchToken('ASSIGN'),
        cmb.Ref(VALUE),
    )
    nodeable = True


class PARAMETERS(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.Separator(
            sep=lexer.Token.COMMA,
            values=[cmb.Ref(PAIR_DECLARE_PARAM), cmb.Ref(PAIR_PARAM)],
        ),
    )
    nodeable = True


class ARGUMENTS(cmb.RuleItem):
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
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('return'),
        cmb.Opt(cmb.Ref(VALUE)),
    )
    nodeable = True


__all__ = [
    'ALIAS',
    'ARGUMENTS',
    'ARRAY',
    'PAIR_DECLARE_PARAM',
    'PAIR_PARAM',
    'PARAMETERS',
    'RETURN',
    'VALUE',
]
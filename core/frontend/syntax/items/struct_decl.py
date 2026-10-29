from gram import combinators as cmb
from gram import lexer

from core.frontend.syntax.items.var_decl import VAR_DECLARATION, VAR_INITIALIZATION
from core.frontend.syntax.items.value import TYPE


class ALIGNMENT(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('AT'),
        cmb.MatchKeyword('align'),
        cmb.Enclosed(
            open=lexer.Token.LPAREN,
            close=lexer.Token.RPAREN,
            content=cmb.MatchToken('NUMBER'),
            allow_empty=False,
            skip_whitespace=True,
        )
    )
    nodeable = True

class AGGREGATE_DECORATOR(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(ALIGNMENT),
        cmb.Seq(
            cmb.MatchToken('AT'),
            cmb.Alt(
                cmb.MatchKeyword('packed'),
                cmb.MatchToken('IDENT'),
            ),
        ),
    )
    nodeable = True


class AGGREGATE_DECORATORS(cmb.RuleItem):
    entrypoint = cmb.Some(cmb.Ref(AGGREGATE_DECORATOR))
    nodeable = True
    
class STRUCT_SIGNATURE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.Opt(cmb.MatchKeyword('volatile')),
        cmb.MatchKeyword('struct'),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('COLON')
    )
    nodeable = True
    
class FLAGS_SIGNATURE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.Opt(cmb.MatchKeyword('volatile')),
        cmb.MatchKeyword('flags'),
        cmb.MatchToken('IDENT'),
        cmb.Ref(TYPE),
        cmb.MatchToken('COLON')
    )
    nodeable = True
    
class MOLD_SIGNATURE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.Opt(cmb.MatchKeyword('volatile')),
        cmb.MatchKeyword('mold'),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('COLON')
    )
    nodeable = True
    
    
class STRUCT_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(VAR_INITIALIZATION),
                cmb.MatchKeyword('pass')
            )
        ),
        cmb.MatchToken('DEDENT'),
    )
    nodeable = True
    

class FLAGS_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(VAR_DECLARATION),
                cmb.MatchKeyword('pass')
            )
        ),
        cmb.MatchToken('DEDENT'),
    )
    nodeable = True 
    
   
class MOLD_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(VAR_INITIALIZATION),
                cmb.MatchKeyword('pass')
            )
        ),
        cmb.MatchToken('DEDENT'),
    )
    nodeable = True
    

class STRUCT(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.Ref(AGGREGATE_DECORATORS)),
        cmb.Ref(STRUCT_SIGNATURE),
        cmb.Ref(STRUCT_BODY),
    )
    nodeable = True
class FLAGS(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.Ref(AGGREGATE_DECORATORS)),
        cmb.Ref(FLAGS_SIGNATURE),
        cmb.Ref(FLAGS_BODY),
    )
    nodeable = True
class MOLD(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.Ref(AGGREGATE_DECORATORS)),
        cmb.Ref(MOLD_SIGNATURE),
        cmb.Ref(MOLD_BODY),
    )
    nodeable = True

__all__ = [
    'FLAGS',
    'MOLD',
    'STRUCT'
]

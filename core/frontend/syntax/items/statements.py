from gram import combinators as cmb

from core.frontend.syntax.items.call import CALL
from core.frontend.syntax.items.enum_decl import ENUM
from core.frontend.syntax.items.struct_decl import FLAGS, MOLD, STRUCT
from core.frontend.syntax.items.value import RETURN, TYPE, VALUE
from core.frontend.syntax.items.var_decl import FIELD_DECLARATION, VAR, VAR_ASSIGNATION

class WHILE(cmb.RuleItem):
    nodeable = True
    
class FOR(cmb.RuleItem):
    nodeable = True
    
class IF(cmb.RuleItem):
    nodeable = True
    
class ELIF(cmb.RuleItem):
    nodeable = True

class ELSE(cmb.RuleItem):
    nodeable = True
  
class CONDITION(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Ref(VALUE)
    
class WHILE_SIGNATURE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('while'),
        cmb.Ref(CONDITION),
        cmb.MatchToken('COLON')
    )
    
class IF_SIGNATURE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('if'),
        cmb.Ref(CONDITION),
        cmb.MatchToken('COLON')
    )
    
    
class ELIF_SIGNATURE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('elif'),
        cmb.Ref(CONDITION),
        cmb.MatchToken('COLON')
    )
    
class ELSE_SIGNATURE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('else'),
        cmb.MatchToken('COLON')
    )


class DEL(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('Del'),
        cmb.Ref(VALUE),
    )


class GLOBAL(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('global'),
        cmb.MatchToken('IDENT'),
    )


class SIMPLE_STATEMENT(cmb.RuleItem):
    """Common statement alternatives shared by function and control bodies."""

    nodeable = False
    entrypoint = cmb.Alt(
        cmb.Ref(ENUM),
        cmb.Ref(FLAGS),
        cmb.Ref(STRUCT),
        cmb.Ref(MOLD),
        cmb.Ref(WHILE),
        cmb.Ref(FOR),
        cmb.Ref(IF),
        cmb.Ref(FIELD_DECLARATION),
        cmb.Ref(VAR_ASSIGNATION),
        cmb.Ref(CALL),
        cmb.Ref(DEL),
        cmb.Ref(GLOBAL),
        cmb.Ref(VAR),
        cmb.Ref(RETURN),
        cmb.MatchGroup('skipers'),
        cmb.MatchKeyword('pass'),
    )
    
class FOR_SIGNATURE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Alt(
        cmb.Seq(
            cmb.MatchKeyword('for'),
            cmb.MatchToken('IDENT'),
            cmb.MatchToken('COLON'),
            cmb.Ref(TYPE),
            cmb.MatchKeyword('ran'),
            cmb.MatchToken('LPAREN'),
            cmb.Ref(VALUE),
            cmb.MatchToken('COMMA'),
            cmb.Ref(VALUE),
            cmb.MatchToken('COMMA'),
            cmb.Ref(VALUE),
            cmb.MatchToken('RPAREN'),
            cmb.MatchToken('COLON'),
        ),
        cmb.Seq(
            cmb.MatchKeyword('for'),
            cmb.MatchToken('IDENT'),
            cmb.MatchToken('COLON'),
            cmb.Ref(TYPE),
            cmb.MatchKeyword('in'),
            cmb.Ref(VALUE),
            cmb.MatchToken('COLON'),
        ),
    )
    
class STATEMENT_BODY(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(cmb.Ref(SIMPLE_STATEMENT)),
        cmb.MatchToken('DEDENT')
    )
    
WHILE.entrypoint = cmb.Seq(
    cmb.Ref(WHILE_SIGNATURE),
    cmb.Ref(STATEMENT_BODY)
)

    
FOR.entrypoint = cmb.Seq(
    cmb.Ref(FOR_SIGNATURE),
    cmb.Ref(STATEMENT_BODY)
)

ELSE.entrypoint = cmb.Seq(
    cmb.Ref(ELSE_SIGNATURE),
    cmb.Ref(STATEMENT_BODY)
)

ELIF.entrypoint = cmb.Seq(
    cmb.Ref(ELIF_SIGNATURE),
    cmb.Ref(STATEMENT_BODY)
)
    
IF.entrypoint = cmb.Seq(
    cmb.Ref(IF_SIGNATURE),
    cmb.Ref(STATEMENT_BODY),
    cmb.Many(cmb.Ref(ELIF)),
    cmb.Opt(cmb.Ref(ELSE))
)

__all__ = [
    'FOR',
    'IF',
    'SIMPLE_STATEMENT',
    'WHILE',
    'DEL',
    'GLOBAL',
]

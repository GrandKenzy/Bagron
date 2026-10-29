from gram import combinators as cmb

from core.frontend.syntax.items.call import CALL
from core.frontend.syntax.items.enum_decl import ENUM
from core.frontend.syntax.items.struct_decl import FLAGS, MOLD, STRUCT
from core.frontend.syntax.items.value import RETURN, TYPE, VALUE
from core.frontend.syntax.items.var_decl import VAR, VAR_ASSIGNATION

# BASE

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
  
# TODO: Pendiente  
# class SWITCH(cmb.RuleItem):
#     nodeable = True
    
# ENCAPSULAR CONDICIÓN
    
class CONDITION(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Ref(VALUE)
    
# SIGNATUREAS
    
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
    
# for i: uint32 ran (inicio, limite, paso):
class FOR_SIGNATURE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
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
    )
    
# CUERPOS

class STATEMENT_BODY(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(ENUM),
                cmb.Ref(FLAGS),
                cmb.Ref(STRUCT),
                cmb.Ref(MOLD),
                cmb.Ref(WHILE),
                cmb.Ref(FOR),
                cmb.Ref(IF),
                cmb.Ref(VAR_ASSIGNATION),
                cmb.Ref(CALL),
                cmb.Ref(DEL),
                cmb.Ref(VAR),
                cmb.Ref(RETURN),
                cmb.MatchGroup('skipers'),
                cmb.MatchKeyword('pass')
            )
        ),
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
    'WHILE',
    'DEL',
]

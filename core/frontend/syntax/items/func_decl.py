from gram import combinators as cmb

from core.frontend.syntax.items.call import CALL
from core.frontend.syntax.items.enum_decl import ENUM
from core.frontend.syntax.items.statements import DEL, FOR, GLOBAL, IF, WHILE
from core.frontend.syntax.items.struct_decl import FLAGS, MOLD, STRUCT
from core.frontend.syntax.items.value import (
    PARAMETERS,
    POINTER,
    RETURN,
    RETURN_ASM,
    TYPE,
)
from core.frontend.syntax.items.var_decl import VAR, VAR_ASSIGNATION


class DECORATOR(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('AT'),
        cmb.MatchToken('IDENT')
    )
    nodeable = True
    
class DECORATORS(cmb.RuleItem):
    entrypoint = cmb.Some(cmb.Ref(DECORATOR))
    nodeable = True
    
# PRIVACY INLINE FUNC IDENT(PARAMETERS) TYPE [POINTER]:
class FUNCTION_SIGNATURE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.Opt(cmb.MatchKeyword('inline')),
        cmb.MatchKeyword('func'),
        cmb.MatchToken('IDENT'),
        cmb.Ref(PARAMETERS),
        cmb.Ref(TYPE),
        cmb.Opt(cmb.Ref(POINTER)),
        cmb.MatchToken('COLON')
    )
    nodeable = True
    
class FUNCTION_BODY(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(STRUCT),
                cmb.Ref(FLAGS),
                cmb.Ref(MOLD),
                cmb.Ref(IF),
                cmb.Ref(WHILE),
                cmb.Ref(ENUM),
                cmb.Ref(FOR),
                cmb.Ref(VAR_ASSIGNATION),
                cmb.Ref(CALL),
                cmb.Ref(DEL),
                cmb.Ref(GLOBAL),
                cmb.Ref(VAR),
                cmb.Ref(RETURN_ASM),
                cmb.Ref(RETURN),
                cmb.MatchGroup('skipers'),
                cmb.MatchKeyword('pass')
                
            )
        ),
        cmb.MatchToken('DEDENT')
    )
    
class FUNCTION(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.Ref(DECORATORS)),
        cmb.Ref(FUNCTION_SIGNATURE),
        cmb.Ref(FUNCTION_BODY)
    )
    
__all__ = [
    'FUNCTION',
    'FUNCTION_BODY'
]

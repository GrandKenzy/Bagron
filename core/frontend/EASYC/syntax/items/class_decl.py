from gram import combinators as cmb
from gram import lexer

from core.frontend.EASYC.syntax.items.call import CALL
from core.frontend.EASYC.syntax.items.enum_decl import ENUM
from core.frontend.EASYC.syntax.items.func_decl import DECORATORS, FUNCTION
from core.frontend.EASYC.syntax.items.statements import FOR, IF, WHILE
from core.frontend.EASYC.syntax.items.struct_decl import FLAGS, MOLD, STRUCT
from core.frontend.EASYC.syntax.items.value import RETURN
from core.frontend.EASYC.syntax.items.var_decl import VAR


class CLASS_HERENCY(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.Separator(
            sep=lexer.Token.COMMA,
            values=[cmb.MatchToken('IDENT')],
        ),
    )
    nodeable = True

class CLASS_SIGNATURE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.MatchKeyword('class'),
        cmb.MatchToken('IDENT'),
        cmb.Opt(cmb.Ref(CLASS_HERENCY)),
        cmb.MatchToken('COLON')
    )
    
class CLASS_BODY(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(FUNCTION),
                cmb.Ref(STRUCT),
                cmb.Ref(FLAGS),
                cmb.Ref(MOLD),
                cmb.Ref(IF),
                cmb.Ref(WHILE),
                cmb.Ref(ENUM),
                cmb.Ref(FOR),
                cmb.Ref(CALL),
                cmb.Ref(VAR),
                cmb.Ref(RETURN),
                cmb.MatchKeyword('pass')
            )
        ),
        cmb.MatchToken('DEDENT')
    )
    
    
class CLASS(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.Ref(DECORATORS)),
        cmb.Ref(CLASS_SIGNATURE),
        cmb.Ref(CLASS_BODY)        
    )
    
__all__ = [
    'CLASS'
]
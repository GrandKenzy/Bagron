from gram import combinators as cmb
from gram import lexer

from core.frontend.EASYC.syntax.items.call import CALL
from core.frontend.EASYC.syntax.items.enum_decl import ENUM
from core.frontend.EASYC.syntax.items.struct_decl import FLAGS, MOLD, STRUCT
from core.frontend.EASYC.syntax.items.value import RETURN, VALUE
from core.frontend.EASYC.syntax.items.var_decl import VAR

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
    
# FOR VARIANTS

class FOR_IDENT_IDENT(cmb.RuleItem):
    entrypoint = cmb.Separator(
        values=[lexer.Token.IDENT],
        allow_trailing=False
    )
    nodeable = False

class FOR_UNPACKED_IDENTS(cmb.RuleItem):
    nodeable = False
    entrypoint = cmb.Alt(
        cmb.Ref(FOR_IDENT_IDENT),
        cmb.Enclosed(
            open=lexer.Token.LPAREN,
            close=lexer.Token.RPAREN,
            content=cmb.Ref(FOR_IDENT_IDENT),
            allow_empty=False
        )
    )

class FOR_VALUE_VALUE(cmb.RuleItem):
    entrypoint = cmb.Separator(
        values=[cmb.Ref(VALUE)],
        allow_trailing=False
    )
    nodeable = False

class FOR_PACKED_VALUES(cmb.RuleItem):
    nodeable = False
    entrypoint = cmb.Alt(
        cmb.Ref(FOR_VALUE_VALUE),
        cmb.Enclosed(
            open=lexer.Token.LPAREN,
            close=lexer.Token.RPAREN,
            content=cmb.Ref(FOR_VALUE_VALUE),
            allow_empty=False
        )
    )


# for a, b, c
# for a
class FOR_SIGNATURE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('for'),
        cmb.Alt(
            cmb.Ref(FOR_UNPACKED_IDENTS),
            cmb.MatchToken('IDENT')
        ),
        cmb.MatchGroup('iters'),
        cmb.Alt(
            cmb.Ref(FOR_PACKED_VALUES),
            cmb.Ref(VALUE)
        ),
        cmb.MatchToken('COLON'),
    )
    
# CUERPOS

class STATEMENT_BODY(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(ENUM),
                cmb.Ref(FLAGS),
                cmb.Ref(STRUCT),
                cmb.Ref(MOLD),
                cmb.Ref(WHILE),
                cmb.Ref(FOR),
                cmb.Ref(IF),
                cmb.Ref(CALL),
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
    cmb.Ref(WHILE_SIGNATURE),
    cmb.Ref(STATEMENT_BODY),
    cmb.Many(cmb.Ref(ELIF)),
    cmb.Opt(cmb.Ref(ELSE))
)

__all__ = [
    'FOR',
    'IF',
    'WHILE',
]
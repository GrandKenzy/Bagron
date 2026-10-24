from gram import combinators as cmb
from gram import lexer

from core.frontend.C.syntax.items.call import CALL, CALL_STMT
from core.frontend.C.syntax.items.enum_decl import ENUM
from core.frontend.C.syntax.items.func_decl import FUNCTION
from core.frontend.C.syntax.items.imports import INCLUDE, PRAGMA
from core.frontend.C.syntax.items.statements import DO_WHILE, FOR, IF, WHILE
from core.frontend.C.syntax.items.struct_decl import STRUCT, UNION
from core.frontend.C.syntax.items.typealias_decl import TYPEDEF
from core.frontend.C.syntax.items.value import VALUE
from core.frontend.C.syntax.items.var_decl import VAR, VAR_ASSIGNATION


class DUEXPR(cmb.RuleItem):
    nodeable = False
    entrypoint = cmb.DualExpr(
        [
            cmb.Ref(CALL),
            lexer.Token.IDENT,
            lexer.Token.NUMBER,
            lexer.Token.NULL,
            lexer.Token.BOOL,
            lexer.Token.STRING,
            lexer.Token.CHAR,
        ]
    )


VALUE.entrypoint = cmb.Alt(
    cmb.Ref(DUEXPR),
    cmb.Ref(CALL),
    cmb.MatchToken('BOOL'),
    cmb.MatchToken('NULL'),
    cmb.MatchToken('IDENT'),
    cmb.MatchToken('STRING'),
    cmb.MatchToken('CHAR'),
    cmb.MatchToken('NUMBER'),
)


class ENTRYPOINT(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(INCLUDE),
        cmb.Ref(PRAGMA),
        cmb.Ref(TYPEDEF),
        cmb.Ref(STRUCT),
        cmb.Ref(UNION),
        cmb.Ref(ENUM),
        cmb.Ref(FUNCTION),
        cmb.Ref(VAR),
        cmb.Ref(VAR_ASSIGNATION),
        cmb.Ref(CALL_STMT),
        cmb.Ref(WHILE),
        cmb.Ref(DO_WHILE),
        cmb.Ref(FOR),
        cmb.Ref(IF),
    )


from core.frontend.C.syntax import C_SESSION

C_SESSION.entrypoint = ENTRYPOINT

__all__ = [
    'C_SESSION',
    'ENTRYPOINT',
]
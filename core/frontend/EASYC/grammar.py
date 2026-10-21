from gram import combinators as cmb
from gram import lexer

from core.frontend.EASYC.syntax.items.call import CALL
from core.frontend.EASYC.syntax.items.class_decl import CLASS
from core.frontend.EASYC.syntax.items.clauses import CLAUSE
from core.frontend.EASYC.syntax.items.enum_decl import ENUM
from core.frontend.EASYC.syntax.items.func_decl import FUNCTION
from core.frontend.EASYC.syntax.items.imports import IMPORT, INCLUDE
from core.frontend.EASYC.syntax.items.statements import FOR, IF, WHILE
from core.frontend.EASYC.syntax.items.struct_decl import FLAGS, MOLD, STRUCT
from core.frontend.EASYC.syntax.items.typealias_decl import TYPEALIAS
from core.frontend.EASYC.syntax.items.value import VALUE
from core.frontend.EASYC.syntax.items.var_decl import VAR


class DUEXPR(cmb.RuleItem):
    nodeable = False
    entrypoint = cmb.DualExpr(
        [cmb.Ref(CALL),
        lexer.Token.IDENT, lexer.Token.NUMBER, lexer.Token.NULL, lexer.Token.BOOL, lexer.Token.STRING]
    )

VALUE.entrypoint = cmb.Alt(
    cmb.Ref(DUEXPR),
    # cmb.Ref(INDEX_ACCESS),
    cmb.Ref(CALL),
    # cmb.Ref(MEMBER_CHAIN),
    cmb.MatchToken('BOOL'),
    cmb.MatchToken('NULL'),
    cmb.MatchToken('IDENT'),
    cmb.MatchToken('STRING'),
    cmb.MatchToken('NUMBER'),
    cmb.MatchToken('DOCSTRING'),
)



class ENTRYPOINT(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(IMPORT),
        cmb.Ref(INCLUDE),
        # cmb.Ref(OBJECT),
        cmb.Ref(CLAUSE),
        cmb.Ref(FUNCTION),
        cmb.Ref(CLASS),
        cmb.Ref(STRUCT),
        cmb.Ref(MOLD),
        cmb.Ref(FLAGS),
        cmb.Ref(TYPEALIAS),
        cmb.Ref(ENUM),
        cmb.Ref(WHILE),
        cmb.Ref(FOR),
        cmb.Ref(IF),
        cmb.Ref(CALL),
        cmb.Ref(VAR)
    )
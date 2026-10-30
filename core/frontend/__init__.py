from gram import combinators as cmb
from gram import lexer
from gram.core.combinators.expressions import ARITHMETIC_UNARY_OPS
from gram.core.lexer.tokens import Token

from core.frontend.syntax.items.call import CALL
from core.frontend.syntax.items.class_decl import CLASS
from core.frontend.syntax.items.clauses import CLAUSE
from core.frontend.syntax.items.enum_decl import ENUM
from core.frontend.syntax.items.externs import EXTERN
from core.frontend.syntax.items.func_decl import FUNCTION
from core.frontend.syntax.items.imports import IMPORT
from core.frontend.syntax.items.statements import FOR, IF, WHILE
from core.frontend.syntax.items.struct_decl import FLAGS, MOLD, STRUCT
from core.frontend.syntax.items.value import LOGICAL_NOT, POSTFIX_EXPR, VALUE
from core.frontend.syntax.items.var_decl import VAR, VAR_ASSIGNATION


class DUEXPR(cmb.RuleItem):
    nodeable = False
    entrypoint = cmb.DualExpr(
        cmb.Ref(LOGICAL_NOT),
        cmb.Ref(POSTFIX_EXPR),
    )


# `$value` is Bagron's explicit address-of operator.  It is registered in
# Gram's prefix table, while `&` remains the existing binary bitwise AND.
# The maps are intentionally mutable in Gram, so this does not require
# changing the vendored parser dependency.
ARITHMETIC_UNARY_OPS[Token.DOLLAR] = 150


DUEXPR.entrypoint.refs_before_grouping = True

VALUE.entrypoint = cmb.Alt(
    cmb.Ref(DUEXPR),
)



class ENTRYPOINT(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(VAR_ASSIGNATION),
        cmb.Ref(IMPORT),
        cmb.Ref(EXTERN),
        cmb.Ref(CLAUSE),
        cmb.Ref(FUNCTION),
        cmb.Ref(CLASS),
        cmb.Ref(STRUCT),
        cmb.Ref(MOLD),
        cmb.Ref(FLAGS),
        cmb.Ref(ENUM),
        cmb.Ref(WHILE),
        cmb.Ref(FOR),
        cmb.Ref(IF),
        cmb.Ref(CALL),
        cmb.Ref(VAR),
    )


    
from core.frontend.syntax import BAGRON_SESSION

BAGRON_SESSION.entrypoint = ENTRYPOINT

__all__ = [
    'BAGRON_SESSION',
    'ENTRYPOINT'
]

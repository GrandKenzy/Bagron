from gram import lexer

from core.initiator.rules.call import CALL, INDEX_ACCESS, MEMBER_CHAIN
from core.initiator.rules.class_decl import CLASS
from core.initiator.rules.clauses import CLAUSE
from core.initiator.rules.enum_decl import ENUM
from core.initiator.rules.expression import DUALEXPR
from core.initiator.rules.flags_decl import FLAGS
from core.initiator.rules.func_decl import DECORATED_FUNCTION, FUNCTION
from core.initiator.rules.imports import IMPORT, INCLUDE, OBJECT
from core.initiator.rules.loops import FOR, FOR_BODY, SKIPER, WHILE, WHILE_BODY
from core.initiator.rules.mold_decl import MOLD
from core.initiator.rules.statement import IF
from core.initiator.rules.struct_decl import STRUCT
from core.initiator.rules.type_decl import TYPEALIAS
from core.initiator.rules.value import RETURN, VALUE, cmb
from core.initiator.rules.var_decl import VAR_ASSIGNATION, VAR_DECL

VALUE.entrypoint = cmb.Alt(
    cmb.Ref(DUALEXPR),
    cmb.Ref(INDEX_ACCESS),
    cmb.Ref(CALL),
    cmb.Ref(MEMBER_CHAIN),
    cmb.MatchToken('IDENT'),
    cmb.MatchToken('STRING'),
    cmb.MatchToken('NUMBER'),
    cmb.MatchToken('DOCSTRING'),
    cmb.MatchToken('BOOL'),
    cmb.MatchToken('NULL'),
)

DUALEXPR.entrypoint = cmb.DualExpr(
    cmb.Ref(INDEX_ACCESS),
    cmb.Ref(CALL),
    cmb.Ref(MEMBER_CHAIN),
    lexer.Token.IDENT,
    lexer.Token.STRING,
    lexer.Token.NUMBER,
    lexer.Token.BOOL,
    lexer.Token.NULL,
)

WHILE_BODY.entrypoint = cmb.Seq(
    cmb.MatchToken('INDENT'),
    cmb.Some(
        cmb.Alt(
            cmb.Ref(VAR_DECL),
            cmb.Ref(VAR_ASSIGNATION),
            cmb.Ref(MEMBER_CHAIN),
            cmb.Ref(CALL),
            cmb.Ref(WHILE),
            cmb.Ref(FOR),
            cmb.Ref(IF),
            cmb.Ref(RETURN),
            cmb.Ref(SKIPER),
            cmb.MatchKeyword('pass'),
        )
    ),
    cmb.MatchToken('DEDENT'),
)

FOR_BODY.entrypoint = cmb.Seq(
    cmb.MatchToken('INDENT'),
    cmb.Some(
        cmb.Alt(
            cmb.Ref(VAR_DECL),
            cmb.Ref(VAR_ASSIGNATION),
            cmb.Ref(MEMBER_CHAIN),
            cmb.Ref(CALL),
            cmb.Ref(WHILE),
            cmb.Ref(FOR),
            cmb.Ref(IF),
            cmb.Ref(RETURN),
            cmb.Ref(SKIPER),
            cmb.MatchKeyword('pass'),
        )
    ),
    cmb.MatchToken('DEDENT'),
)

class ENTRYPOINT(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(IMPORT),
        cmb.Ref(INCLUDE),
        cmb.Ref(OBJECT),
        cmb.Ref(CLAUSE),
        cmb.Ref(DECORATED_FUNCTION),
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
        cmb.Ref(VAR_DECL),
        cmb.Ref(VAR_ASSIGNATION),
        cmb.Ref(MEMBER_CHAIN),
        cmb.Ref(CALL),
    )
from gram import combinators as cmb

from core.frontend.syntax.items.call import CALL
from core.frontend.syntax.items.enum_decl import ENUM
from core.frontend.syntax.items.statements import (
    DEL,
    FOR,
    GLOBAL,
    IF,
    SIMPLE_STATEMENT,
    WHILE,
)
from core.frontend.syntax.items.struct_decl import FLAGS, MOLD, STRUCT
from core.frontend.syntax.items.struct_decl import AGGREGATE_DECORATOR
from core.frontend.syntax.items.value import (
    PARAMETERS,
    POINTER,
    RETURN,
    RETURN_ASM,
    TYPE,
)
from core.frontend.syntax.items.var_decl import FIELD_DECLARATION, VAR, VAR_ASSIGNATION


class DECORATOR(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Seq(
            cmb.MatchToken('AT'),
            cmb.MatchToken('IDENT'),
        ),
        # Aggregate decorators are also valid on class declarations. Keeping
        # them in the shared decorator sequence lets class decorators mix with
        # @frozen without introducing a second AST shape.
        cmb.Ref(AGGREGATE_DECORATOR),
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


class FUNCTION_STATEMENT(cmb.RuleItem):
    """Statements valid in an ordinary function body."""

    nodeable = False
    entrypoint = cmb.Alt(
        cmb.Ref(RETURN_ASM),
        cmb.Ref(SIMPLE_STATEMENT),
    )


class INLINE_FUNCTION_STATEMENT(cmb.RuleItem):
    """One simple statement allowed after a function signature colon."""

    nodeable = False
    entrypoint = cmb.Alt(
        cmb.Ref(CALL),
        cmb.Ref(DEL),
        cmb.Ref(RETURN),
        cmb.MatchKeyword('pass'),
    )
    
class FUNCTION_BODY(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Alt(
        cmb.Seq(
            cmb.MatchToken('INDENT'),
            cmb.Some(cmb.Ref(FUNCTION_STATEMENT)),
            cmb.MatchToken('DEDENT'),
        ),
        cmb.Ref(INLINE_FUNCTION_STATEMENT),
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

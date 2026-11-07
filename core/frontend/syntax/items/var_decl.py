from gram import combinators as cmb

from core.frontend.syntax.items.value import (
    DECLARATOR,
    DEREF_ASSIGN_TARGET,
    DEREF_TARGET,
    INDEX_ACCESS,
    MEMBER_ACCESS,
    POSTFIX_EXPR,
    TYPE,
    VALUE,
)


class ASSIGN_OPERATOR(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.MatchToken('ASSIGN'),
        cmb.MatchToken('PLUS_ASSIGN'),
        cmb.MatchToken('MINUS_ASSIGN'),
        cmb.MatchToken('STAR_ASSIGN'),
        cmb.MatchToken('SLASH_ASSIGN'),
        cmb.MatchToken('PERCENT_ASSIGN'),
        cmb.MatchToken('AND_ASSIGN'),
        cmb.MatchToken('OR_ASSIGN'),
        cmb.MatchToken('XOR_ASSIGN'),
        cmb.MatchToken('SHL_ASSIGN'),
        cmb.MatchToken('SHR_ASSIGN'),
    )
    nodeable = False


class ASSIGN_TARGET(cmb.RuleItem):
    # All lvalue forms share POSTFIX_EXPR.  Parenthesized pointer targets
    # remain distinguishable in the AST through PAREN_VALUE and are resolved
    # semantically as dereferences.
    entrypoint = cmb.Ref(POSTFIX_EXPR)
    nodeable = True


class VAR_DECLARATION(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(DECLARATOR),
        cmb.MatchToken('COLON'),
        cmb.Ref(TYPE),
        cmb.MatchToken('ASSIGN'),
        cmb.Ref(VALUE),
    )
    nodeable = True


class VAR_INITIALIZATION(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(DECLARATOR),
        cmb.MatchToken('COLON'),
        cmb.Ref(TYPE),
    )
    nodeable = True


class VAR(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.Alt(
            cmb.Ref(VAR_DECLARATION),
            cmb.Ref(VAR_INITIALIZATION)
        ),
    )
    nodeable = True


class VAR_ASSIGNATION(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(ASSIGN_TARGET),
        cmb.Ref(ASSIGN_OPERATOR),
        cmb.Ref(VALUE),
    )
    nodeable = True


class MEMBER_ACCESS_TARGET(cmb.RuleItem):
    """Target for direct attribute operations, e.g. ``self.state``."""

    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Some(cmb.Ref(MEMBER_ACCESS)),
    )
    nodeable = True


class FIELD_DECLARATION(cmb.RuleItem):
    """Explicitly-typed instance attribute declaration, e.g. ``self.state: uint32 = 0xFFFFFFFF``."""

    entrypoint = cmb.Seq(
        cmb.Ref(MEMBER_ACCESS_TARGET),
        cmb.MatchToken('COLON'),
        cmb.Ref(TYPE),
        cmb.MatchToken('ASSIGN'),
        cmb.Ref(VALUE),
    )
    nodeable = True


__all__ = [
    'FIELD_DECLARATION',
    'MEMBER_ACCESS_TARGET',
    'VAR',
    'VAR_ASSIGNATION',
    'VAR_DECLARATION',
    'VAR_INITIALIZATION'
]

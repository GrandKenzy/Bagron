from gram import combinators as cmb
from gram.core.lexer import Token

from core.frontend.HEADERS.headers.syntax.items.attributes import ATTRIBUTE_SPECIFIER
from core.frontend.HEADERS.headers.syntax.items.expressions import CONST_EXPR, TYPE_NAME


class TAG_SPECIFIER(cmb.RuleItem):
    pass


class SPECIFIER_PREFIX(cmb.RuleItem):
    pass


class LONG_LONG_TOKEN(cmb.RuleItem):
    entrypoint = cmb.Tokenize(cmb.MatchKeyword('long'), cmb.MatchKeyword('long'), token_name='long long')
    nodeable = True


class SIGNED(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.MatchGroup('signed_'))
    nodeable = True


class ELSEIF_TOKEN(cmb.RuleItem):
    entrypoint = cmb.Tokenize(cmb.MatchKeyword('else'), cmb.MatchKeyword('if'), token_name='else if')
    nodeable = True


class BIT_INT(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('_BitInt'),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Seq(
                cmb.Opt(cmb.Ref(SIGNED)),
                cmb.Ref(CONST_EXPR)
            )
        )
    )
    nodeable = True


class BASIC_TYPE(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(LONG_LONG_TOKEN),
        cmb.Ref(SIGNED),
        cmb.Ref(BIT_INT),
        cmb.MatchGroup('types', values=['_BitInt'], behavior_values='deny')
    )
    nodeable = True


class ATOMIC_QUALIFIER(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('_Atomic'),
        cmb.Not(cmb.Peek(cmb.MatchToken('LPAREN')))
    )
    nodeable = True


class QUALIFIER(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(ATOMIC_QUALIFIER),
        cmb.MatchGroup('qualifiers', values=['_Atomic'], behavior_values='deny')
    )
    nodeable = True


class STORAGE_SPECIFIER(cmb.RuleItem):
    entrypoint = cmb.MatchGroup('storage_specifiers', values=['typedef'], behavior_values='deny')
    nodeable = True


class FUNCTION_SPECIFIER(cmb.RuleItem):
    entrypoint = cmb.MatchGroup('function_specifiers')
    nodeable = True


class ALIGNAS_SPECIFIER(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchGroup('alignment_specifiers'),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Alt(
                cmb.Ref(TYPE_NAME),
                cmb.Ref(CONST_EXPR)
            )
        )
    )
    nodeable = True


class TYPEOF_SPECIFIER(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchGroup('typeof_specifiers'),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Alt(
                cmb.Ref(TYPE_NAME),
                cmb.Ref(CONST_EXPR)
            )
        )
    )
    nodeable = True


class ATOMIC_SPECIFIER(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('_Atomic'),
        cmb.Enclosed(
            open=Token.LPAREN,
            close=Token.RPAREN,
            content=cmb.Ref(TYPE_NAME)
        )
    )
    nodeable = True


class BASIC_TYPE_SPEC(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Many(cmb.Ref(QUALIFIER)),
        cmb.Ref(BASIC_TYPE),
        cmb.Many(
            cmb.Alt(
                cmb.Ref(BASIC_TYPE),
                cmb.Ref(SPECIFIER_PREFIX)
            )
        )
    )
    nodeable = True


class ALIASED_TYPE(cmb.RuleItem):
    entrypoint = cmb.MatchToken('IDENT')
    nodeable = True


class ALIASED_TYPE_SPEC(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Many(cmb.Ref(QUALIFIER)),
        cmb.Ref(ALIASED_TYPE),
        cmb.Many(cmb.Ref(QUALIFIER))
    )
    nodeable = True


class TYPE_SPEC(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(ATOMIC_SPECIFIER),
        cmb.Ref(TYPEOF_SPECIFIER),
        cmb.Ref(TAG_SPECIFIER),
        cmb.Ref(BASIC_TYPE_SPEC),
        cmb.Ref(ALIASED_TYPE_SPEC)
    )
    nodeable = True


SPECIFIER_PREFIX.entrypoint = cmb.Alt(
    cmb.Ref(STORAGE_SPECIFIER),
    cmb.Ref(FUNCTION_SPECIFIER),
    cmb.Ref(ALIGNAS_SPECIFIER),
    cmb.Ref(ATTRIBUTE_SPECIFIER),
    cmb.Ref(QUALIFIER)
)
SPECIFIER_PREFIX.nodeable = True


class DECL_SPECIFIERS(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Many(cmb.Ref(SPECIFIER_PREFIX)),
        cmb.Ref(TYPE_SPEC),
        cmb.Many(cmb.Ref(SPECIFIER_PREFIX))
    )
    nodeable = True


__all__ = [
    'ALIASED_TYPE',
    'ALIASED_TYPE_SPEC',
    'ALIGNAS_SPECIFIER',
    'ATOMIC_QUALIFIER',
    'ATOMIC_SPECIFIER',
    'BASIC_TYPE',
    'BASIC_TYPE_SPEC',
    'BIT_INT',
    'DECL_SPECIFIERS',
    'ELSEIF_TOKEN',
    'FUNCTION_SPECIFIER',
    'LONG_LONG_TOKEN',
    'QUALIFIER',
    'SIGNED',
    'SPECIFIER_PREFIX',
    'STORAGE_SPECIFIER',
    'TAG_SPECIFIER',
    'TYPEOF_SPECIFIER',
    'TYPE_SPEC',
]

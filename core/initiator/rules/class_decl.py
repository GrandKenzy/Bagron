from gram import combinators as cmb
from gram import lexer

from core.initiator.rules.call import CALL
from core.initiator.rules.func_decl import DECORATOR, DECORATORS, FUNCTION
from core.initiator.rules.var_decl import VAR_ASSIGNATION, VAR_DECL


class CLASS_HERENCY(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.Separator(
            sep=lexer.Token.COMMA,
            values=[cmb.Ref(CALL), cmb.MatchToken('IDENT')],
        ),
    )
    nodeable = True


class CLASS_FIRM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.MatchKeyword('class'),
        cmb.MatchToken('IDENT'),
        cmb.Opt(cmb.Ref(CLASS_HERENCY)),
        cmb.MatchToken('COLON'),
    )
    nodeable = True


class CLASS_METHOD(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.Ref(DECORATORS)),
        cmb.Ref(FUNCTION),
    )
    nodeable = True


class CLASS_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(CLASS_METHOD),
                cmb.Ref(VAR_DECL),
                cmb.Ref(VAR_ASSIGNATION),
                cmb.MatchKeyword('pass'),
            )
        ),
        cmb.MatchToken('DEDENT'),
    )
    nodeable = True


class CLASS(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.Ref(DECORATORS)),
        cmb.Ref(CLASS_FIRM),
        cmb.Ref(CLASS_BODY),
    )
    nodeable = True


__all__ = [
    'CLASS',
    'CLASS_BODY',
    'CLASS_FIRM',
    'CLASS_HERENCY',
    'CLASS_METHOD',
]
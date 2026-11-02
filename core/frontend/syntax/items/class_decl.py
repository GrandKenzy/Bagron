from gram import combinators as cmb
from gram import lexer

from core.frontend.syntax.items.func_decl import DECORATORS, FUNCTION


class CLASS_HERENCY(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=cmb.MatchToken('IDENT'),
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
    
class CLASS_MEMBER(cmb.RuleItem):
    nodeable = False
    entrypoint = cmb.Alt(
        cmb.Ref(FUNCTION),
        cmb.MatchKeyword('pass')
    )


class NEXT_CLASS_MEMBER(cmb.RuleItem):
    nodeable = False
    entrypoint = cmb.Alt(
        cmb.Seq(
            cmb.Many(cmb.MatchToken('NEWLINE')),
            cmb.Not(cmb.SameLine(cmb.Peek(cmb.Ref(CLASS_MEMBER)))),
            cmb.Ref(CLASS_MEMBER),
        ),
        cmb.Seq(cmb.Expected.newline(), cmb.Ref(CLASS_MEMBER)),
    )


class CLASS_BODY(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken('NEWLINE'),
        cmb.MatchToken('INDENT'),
        cmb.Ref(CLASS_MEMBER),
        cmb.Many(cmb.Ref(NEXT_CLASS_MEMBER)),
        cmb.Many(cmb.MatchToken('NEWLINE')),
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

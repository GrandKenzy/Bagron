import gram
from core.initiator.rules.expression import EGL_EXPRESSION
from core.initiator.rules.statement import EGL_STMT_BODY

class EGL_LOOP_MODE(gram.RuleItem):
    name = 'EGL_LOOP_MODE'
    code = gram.AutoCode()
    grammar = gram.Alt(
        gram.Seq(gram.MatchKeyword('in'), gram.MatchKeyword('ran')),
        gram.Seq(gram.MatchKeyword('in'), gram.MatchKeyword('rand')),
        gram.MatchKeyword('ran'),
        gram.MatchKeyword('rand'),
        gram.MatchKeyword('in'),
    )

class EGL_FOR_STATEMENT(gram.RuleItem):
    name = 'EGL_FOR_STATEMENT'
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('for'),
        gram.MatchToken('IDENT'),
        gram.Ref(EGL_LOOP_MODE),
        gram.Separator(
            sep=gram.Token.COMMA,
            values=[gram.Ref(EGL_EXPRESSION)],
            min=1,
            allow_trailing=False,
        ),
        gram.Ref(EGL_STMT_BODY),
    )

FOR_Statement = EGL_FOR_STATEMENT
Loop_Mode = EGL_LOOP_MODE

__all__ = [
    'EGL_LOOP_MODE',
    'EGL_FOR_STATEMENT',
    'FOR_Statement',
    'Loop_Mode',
]

import gram
from core.initiator.rules.expression import EGL_EXPRESSION
from core.initiator.rules.statement import EGL_STMT_BODY

class EGL_LOOP_MODE(gram.RuleItem):
    name = 'EGL_LOOP_MODE'
    code = gram.AutoCode()
    grammar = gram.Alt(
        gram.MatchKeyword('ran'),
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

class EGL_WHILE_COND(gram.RuleItem):
    name = 'EGL_WHILE_COND'
    code = gram.AutoCode()
    no_simplify = True
    grammar = gram.Ref(EGL_EXPRESSION)

class EGL_WHILE_STATEMENT(gram.RuleItem):
    name = 'EGL_WHILE_STATEMENT'
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('while'),
        gram.Ref(EGL_WHILE_COND),
        gram.Ref(EGL_STMT_BODY),
    )

__all__ = [
    'EGL_LOOP_MODE',
    'EGL_FOR_STATEMENT',
    'EGL_WHILE_COND',
    'EGL_WHILE_STATEMENT',
]

import gram
from core.initiator.rules.expression import EGL_EXPRESSION
from core.initiator.rules.var_decl import EGL_VAR_DECL
from core.initiator.rules.value import EGL_VALUE
from core.initiator.rules.call import EGL_CALL, EGL_METHOD_CALL, EGL_MEMBER_ACCESS

class EGL_CONDITION(gram.RuleItem):
    name = 'EGL_CONDITION'
    code = gram.AutoCode()
    no_simplify = True
    grammar = gram.Ref(EGL_EXPRESSION)

class EGL_RETURN(gram.RuleItem):
    name = 'EGL_RETURN'
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('return'),
        gram.Ref(EGL_VALUE)
    )

class EGL_ASSIGN(gram.RuleItem):
    name = 'EGL_ASSIGN'
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Alt(
            gram.Seq(
                gram.MatchKeyword('this'),
                gram.MatchToken(gram.Token.DOT),
                gram.MatchToken('IDENT'),
            ),
            gram.MatchToken('IDENT'),
        ),
        gram.MatchToken('ASSIGN'),
        gram.Ref(EGL_VALUE),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

class EGL_STATEMENT(gram.RuleItem):
    name = 'EGL_STATEMENT'
    code = gram.AutoCode()
    ignore = True
    grammar = None

class EGL_STMT_BODY(gram.RuleItem):
    name = 'EGL_STMT_BODY'
    code = gram.AutoCode()
    grammar = gram.Alt(
        gram.Seq(
            gram.MatchToken('COLON'),
            gram.MatchToken('INDENT'),
            gram.Some(
                gram.Ref(EGL_STATEMENT)
            ),
            gram.MatchToken('DEDENT')
        ),
        gram.Seq(
            gram.MatchToken('LBRACE'),
            gram.Opt(gram.MatchToken('INDENT')),
            gram.Some(
                gram.Ref(EGL_STATEMENT)
            ),
            gram.Opt(gram.MatchToken('DEDENT')),
            gram.MatchToken('RBRACE')
        )
    )

class EGL_ELIF_STATEMENT(gram.RuleItem):
    name = 'EGL_ELIF_STATEMENT'
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('elif'),
        gram.Ref(EGL_CONDITION),
        gram.Ref(EGL_STMT_BODY)
    )

class EGL_ELSE_STATEMENT(gram.RuleItem):
    name = 'EGL_ELSE_STATEMENT'
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('else'),
        gram.Ref(EGL_STMT_BODY)
    )

class EGL_IF_STATEMENT(gram.RuleItem):
    name = 'EGL_IF_STATEMENT'
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('if'),
        gram.Ref(EGL_CONDITION),
        gram.Ref(EGL_STMT_BODY),
        gram.Many(
            gram.Ref(EGL_ELIF_STATEMENT)
        ),
        gram.Opt(
            gram.Ref(EGL_ELSE_STATEMENT)
        )
    )

from core.initiator.rules.loops import EGL_FOR_STATEMENT

EGL_STATEMENT.grammar = gram.Alt(
    gram.Ref(EGL_IF_STATEMENT),
    gram.Ref(EGL_FOR_STATEMENT),
    gram.Ref(EGL_VAR_DECL),
    gram.Ref(EGL_RETURN),
    gram.Ref(EGL_ASSIGN),
    gram.Ref(EGL_METHOD_CALL),
    gram.Ref(EGL_MEMBER_ACCESS),
    gram.Ref(EGL_CALL),
    gram.MatchToken('COMMENT'),
    gram.MatchKeyword('pass'),
)

Condition = EGL_CONDITION
EC_RETURN = EGL_RETURN
EC_ASSIGN = EGL_ASSIGN
EC_STATEMENT = EGL_STATEMENT
EC_STMT_BODY = EGL_STMT_BODY
ELIF_Statement = EGL_ELIF_STATEMENT
ELSE_Statement = EGL_ELSE_STATEMENT
IF_Statement = EGL_IF_STATEMENT

__all__ = [
    'EGL_CONDITION',
    'EGL_RETURN',
    'EGL_ASSIGN',
    'EGL_STATEMENT',
    'EGL_STMT_BODY',
    'EGL_ELIF_STATEMENT',
    'EGL_ELSE_STATEMENT',
    'EGL_IF_STATEMENT',
    'EGL_FOR_STATEMENT',
    'Condition',
    'EC_RETURN',
    'EC_ASSIGN',
    'EC_STATEMENT',
    'EC_STMT_BODY',
    'ELIF_Statement',
    'ELSE_Statement',
    'IF_Statement',
]
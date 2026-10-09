import gram
from gram.plugins.source import expressions as GramExpr

def _left_chain(rule: type[gram.RuleItem], operator_tokens: tuple[gram.Token, ...]):
    return GramExpr.ChainL(
        gram.Ref(rule),
        gram.Alt(*(gram.MatchToken(token) for token in operator_tokens)),
        reducer=lambda left, operator, right: [left, operator, right],
    )

def _right_chain(rule: type[gram.RuleItem], operator_tokens: tuple[gram.Token, ...]):
    return GramExpr.ChainR(
        gram.Ref(rule),
        gram.Alt(*(gram.MatchToken(token) for token in operator_tokens)),
        reducer=lambda left, operator, right: [left, operator, right],
    )

class EGL_EXPRESSION(gram.RuleItem):
    name = 'EGL_EXPRESSION'
    code = gram.AutoCode()

class EGL_LOGICAL_AND(gram.RuleItem):
    name = 'EGL_LOGICAL_AND'
    code = gram.AutoCode()

class EGL_BITWISE_OR(gram.RuleItem):
    name = 'EGL_BITWISE_OR'
    code = gram.AutoCode()

class EGL_BITWISE_XOR(gram.RuleItem):
    name = 'EGL_BITWISE_XOR'
    code = gram.AutoCode()

class EGL_BITWISE_AND(gram.RuleItem):
    name = 'EGL_BITWISE_AND'
    code = gram.AutoCode()

class EGL_EQUALITY(gram.RuleItem):
    name = 'EGL_EQUALITY'
    code = gram.AutoCode()

class EGL_COMPARISON(gram.RuleItem):
    name = 'EGL_COMPARISON'
    code = gram.AutoCode()

class EGL_SHIFT(gram.RuleItem):
    name = 'EGL_SHIFT'
    code = gram.AutoCode()

class EGL_ADDITIVE(gram.RuleItem):
    name = 'EGL_ADDITIVE'
    code = gram.AutoCode()

class EGL_MULTIPLICATIVE(gram.RuleItem):
    name = 'EGL_MULTIPLICATIVE'
    code = gram.AutoCode()

class EGL_POWER(gram.RuleItem):
    name = 'EGL_POWER'
    code = gram.AutoCode()

class EGL_UNARY(gram.RuleItem):
    name = 'EGL_UNARY'
    code = gram.AutoCode()

class EGL_PRIMARY(gram.RuleItem):
    name = 'EGL_PRIMARY'
    code = gram.AutoCode()

EGL_PRIMARY.grammar = gram.Alt(
    gram.MatchToken(gram.Token.NUMBER),
    gram.MatchToken(gram.Token.STRING),
    gram.MatchToken(gram.Token.CHAR),
    gram.MatchToken(gram.Token.BOOL),
    gram.MatchToken(gram.Token.NULL),
    gram.MatchToken(gram.Token.IDENT),
    gram.MatchGroup('types'),
    gram.MatchKeyword('this'),
    gram.Enclosed(
        open=gram.Token.LPAREN,
        content=gram.Ref(EGL_EXPRESSION),
        close=gram.Token.RPAREN,
        allow_empty=False,
    ),
)

EGL_UNARY.grammar = gram.Alt(
    gram.Seq(
        gram.Alt(
            gram.MatchToken(gram.Token.PLUS),
            gram.MatchToken(gram.Token.MINUS),
            gram.MatchToken(gram.Token.NOT_LOGIC),
            gram.MatchToken(gram.Token.NOT),
            gram.MatchKeyword('not'),
        ),
        gram.Ref(EGL_UNARY),
    ),
    gram.Ref(EGL_PRIMARY),
)

EGL_POWER.grammar = _right_chain(EGL_UNARY, (gram.Token.POW,))
EGL_MULTIPLICATIVE.grammar = _left_chain(
    EGL_POWER,
    (
        gram.Token.STAR,
        gram.Token.SLASH,
        gram.Token.FLOOR_DIV,
        gram.Token.PERCENT,
    ),
)
EGL_ADDITIVE.grammar = _left_chain(
    EGL_MULTIPLICATIVE,
    (gram.Token.PLUS, gram.Token.MINUS),
)
EGL_SHIFT.grammar = _left_chain(
    EGL_ADDITIVE,
    (gram.Token.SHL, gram.Token.SHR),
)
EGL_COMPARISON.grammar = _left_chain(
    EGL_SHIFT,
    (
        gram.Token.LESS,
        gram.Token.LESS_EQUAL,
        gram.Token.GREATER,
        gram.Token.GREATER_EQUAL,
    ),
)
EGL_EQUALITY.grammar = _left_chain(
    EGL_COMPARISON,
    (gram.Token.EQUAL, gram.Token.NOT_EQUAL),
)
EGL_BITWISE_AND.grammar = _left_chain(
    EGL_EQUALITY,
    (gram.Token.AND,),
)
EGL_BITWISE_XOR.grammar = _left_chain(
    EGL_BITWISE_AND,
    (gram.Token.XOR,),
)
EGL_BITWISE_OR.grammar = _left_chain(
    EGL_BITWISE_XOR,
    (gram.Token.OR,),
)
EGL_LOGICAL_AND.grammar = _left_chain(
    EGL_BITWISE_OR,
    (gram.Token.AND_LOGIC, gram.Token.LOGIC_AND),
)
EGL_EXPRESSION.grammar = _left_chain(
    EGL_LOGICAL_AND,
    (gram.Token.OR_LOGIC, gram.Token.LOGIC_OR),
)

__all__ = [
    'EGL_EXPRESSION',
    'EGL_LOGICAL_AND',
    'EGL_BITWISE_OR',
    'EGL_BITWISE_XOR',
    'EGL_BITWISE_AND',
    'EGL_EQUALITY',
    'EGL_COMPARISON',
    'EGL_SHIFT',
    'EGL_ADDITIVE',
    'EGL_MULTIPLICATIVE',
    'EGL_POWER',
    'EGL_UNARY',
    'EGL_PRIMARY',
]

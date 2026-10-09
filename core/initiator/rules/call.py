import gram
from core.initiator.rules.expression import EGL_EXPRESSION, EGL_PRIMARY
from core.initiator.rules.value import EGL_VALUE

class EGL_NAMED_ARG(gram.RuleItem):
    name = "EGL_NAMED_ARG"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchToken('IDENT'),
        gram.MatchToken('ASSIGN'),
        gram.Ref(EGL_EXPRESSION)
    )

class EGL_ARG_ITEM(gram.RuleItem):
    name = "EGL_ARG_ITEM"
    code = gram.AutoCode()
    grammar = gram.Alt(
        gram.Ref(EGL_NAMED_ARG),
        gram.Ref(EGL_EXPRESSION),
    )

class EGL_ARGUMENTS(gram.RuleItem):
    name = "EGL_ARGUMENTS"
    code = gram.AutoCode()
    grammar = gram.Separator(
        sep=gram.Token.COMMA,
        values=[gram.Ref(EGL_ARG_ITEM)],
        min=1,
        allow_trailing=False,
    )

class EGL_CALL(gram.RuleItem):
    name = "EGL_CALL"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Alt(
            gram.MatchToken('IDENT'),
            gram.MatchKeyword('__size__'),
        ),
        gram.Enclosed(
            open=gram.Token.LPAREN,
            content=gram.Opt(gram.Ref(EGL_ARGUMENTS)),
            close=gram.Token.RPAREN
        ),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

class EGL_METHOD_CALL(gram.RuleItem):
    name = "EGL_METHOD_CALL"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Alt(
            gram.MatchToken('IDENT'),
            gram.MatchGroup('types'),
            gram.MatchKeyword('this'),
        ),
        gram.MatchToken(gram.Token.DOT),
        gram.MatchToken('IDENT'),
        gram.Enclosed(
            open=gram.Token.LPAREN,
            content=gram.Opt(gram.Ref(EGL_ARGUMENTS)),
            close=gram.Token.RPAREN
        ),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

class EGL_MEMBER_ACCESS(gram.RuleItem):
    name = "EGL_MEMBER_ACCESS"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Alt(
            gram.MatchToken('IDENT'),
            gram.MatchGroup('types'),
            gram.MatchKeyword('this'),
        ),
        gram.MatchToken(gram.Token.DOT),
        gram.MatchToken('IDENT')
    )

_primary_grammar = EGL_PRIMARY.grammar
assert _primary_grammar is not None

EGL_PRIMARY.grammar = gram.Alt(
    gram.Ref(EGL_METHOD_CALL),
    gram.Ref(EGL_MEMBER_ACCESS),
    gram.Ref(EGL_CALL),
    _primary_grammar,
)

EGL_VALUE.grammar = gram.Ref(EGL_EXPRESSION)

__all__ = ['EGL_ARGUMENTS', 'EGL_ARG_ITEM', 'EGL_NAMED_ARG', 'EGL_CALL', 'EGL_METHOD_CALL', 'EGL_MEMBER_ACCESS']
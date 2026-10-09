import gram
from core.initiator.rules.value import EGL_VALUE

class EGL_PARAM(gram.RuleItem):
    name = 'EGL_PARAM'
    code = gram.AutoCode()
    grammar = gram.Alt(
        gram.Seq(
            gram.Alt(
                gram.Seq(
                    gram.MatchKeyword('this'),
                    gram.MatchToken(gram.Token.DOT),
                    gram.MatchToken('IDENT'),
                ),
                gram.MatchGroup('types'),
                gram.MatchToken('IDENT'),
            ),
            gram.Opt(gram.MatchToken(gram.Token.STAR)),
            gram.MatchToken('IDENT'),
            gram.Opt(
                gram.Seq(
                    gram.MatchToken('ASSIGN'),
                    gram.Ref(EGL_VALUE)
                )
            )
        ),
        gram.Seq(
            gram.MatchToken(gram.Token.STAR),
            gram.MatchToken('IDENT'),
            gram.Opt(
                gram.Seq(
                    gram.MatchToken('ASSIGN'),
                    gram.Ref(EGL_VALUE)
                )
            )
        )
    )

class EGL_PARAMS(gram.RuleItem):
    name = 'EGL_PARAMS'
    code = gram.AutoCode()
    grammar = gram.Enclosed(
        open=gram.Token.LPAREN,
        content=gram.Opt(
            gram.Alt(
                gram.Separator(
                    sep=gram.Token.COMMA,
                    values=[
                        gram.Ref(EGL_PARAM)
                    ]
                ),
                gram.MatchKeyword('void')
            ),
        ),
        close=gram.Token.RPAREN
    )

EC_PARAM = EGL_PARAM
EC_PARAMS = EGL_PARAMS
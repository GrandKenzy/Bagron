import gram
from core.initiator.rules.value import EGL_VALUE
from core.initiator.rules.type_spec import EGL_TYPE_SPEC

class EGL_PARAM(gram.RuleItem):
    name = 'EGL_PARAM'
    code = gram.AutoCode()
    grammar = gram.Alt(
        gram.MatchKeyword('self'),
        gram.Seq(
            gram.Ref(EGL_TYPE_SPEC),
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
                gram.MatchKeyword('void'),
                gram.Separator(
                    sep=gram.Token.COMMA,
                    values=[
                        gram.Ref(EGL_PARAM)
                    ]
                )
            ),
        ),
        close=gram.Token.RPAREN
    )
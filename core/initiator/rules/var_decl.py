import gram
from core.initiator.rules.value import EGL_VALUE

class EGL_VAR_DECL(gram.RuleItem):
    name = 'EGL_VAR_DECL'
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Opt(
            gram.MatchGroup('privacity'),
        ),
        gram.Alt(
            gram.MatchGroup('types'),
            gram.MatchToken('IDENT'),
        ),
        gram.Opt(gram.MatchToken(gram.Token.STAR)),
        gram.Opt(
            gram.Enclosed(
                gram.Token.LBRACKET,
                gram.MatchToken('NUMBER'),
                gram.Token.RBRACKET
            )
        ),
        gram.MatchToken('IDENT'),
        gram.Opt(
            gram.Seq(
                gram.MatchToken('ASSIGN'),
                gram.Ref(EGL_VALUE),
            )
        ),
        gram.Opt(
            gram.MatchToken('COMMENT')
        )
    )

EC_VAR_DECL = EGL_VAR_DECL
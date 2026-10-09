import gram
from core.initiator.rules.params import EGL_PARAMS
from core.initiator.rules.statement import EGL_STATEMENT

class EGL_FUNC_BODY(gram.RuleItem):
    name = 'EGL_FUNC_BODY'
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

class EGL_FUNC_DECL(gram.RuleItem):
    name = 'EGL_FUNC_DECL'
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
        gram.MatchToken('IDENT'),
        gram.Ref(EGL_PARAMS),
        gram.Opt(
            gram.MatchToken('COMMENT')
        ),
        gram.Alt(
            gram.Ref(EGL_FUNC_BODY),
        )
    )

EC_FUNC_BODY = EGL_FUNC_BODY
EC_FUNC_DECL = EGL_FUNC_DECL
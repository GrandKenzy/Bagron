import gram
from core.initiator.rules.params import EGL_PARAMS
from core.initiator.rules.type_spec import EGL_TYPE_SPEC

class EXTERN_FUNC(gram.RuleItem):
    name = 'EXTERN_FUNC'
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Ref(EGL_TYPE_SPEC),
        gram.Opt(gram.MatchToken(gram.Token.STAR)),
        gram.MatchToken('IDENT'),
        gram.Ref(EGL_PARAMS),
        gram.Opt(
            gram.Seq(
                gram.MatchKeyword('as'),
                gram.MatchToken('IDENT'),
            )
        ),
    )

extern_grammar = {
    gram.PROGRAM: gram.Many(
        gram.Ref(EXTERN_FUNC)
    )
}

__all__ = ['EXTERN_FUNC', 'extern_grammar']

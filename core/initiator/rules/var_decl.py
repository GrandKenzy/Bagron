import gram
from core.initiator.rules.value import EGL_VALUE
from core.initiator.rules.type_spec import EGL_TYPE_SPEC
from core.initiator.rules.call import EGL_MEMBER_ACCESS

class EGL_VAR_DECL(gram.RuleItem):
    name = 'EGL_VAR_DECL'
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Opt(
            gram.MatchGroup('privacity'),
        ),
        gram.Ref(EGL_TYPE_SPEC),
        gram.Alt(
            gram.Ref(EGL_MEMBER_ACCESS),
            gram.MatchToken('IDENT'),
        ),
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
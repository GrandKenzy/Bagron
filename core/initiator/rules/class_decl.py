import gram
from core.initiator.rules.params import EGL_PARAMS
from core.initiator.rules.func_decl import EGL_FUNC_BODY
from core.initiator.rules.type_spec import EGL_TYPE_SPEC
from core.initiator.rules.var_decl import EGL_VAR_DECL
from core.initiator.rules.statement import EGL_STATEMENT

class EGL_METHOD_DECL(gram.RuleItem):
    name = "EGL_METHOD_DECL"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Opt(
            gram.Seq(
                gram.MatchToken(gram.Token.AT),
                gram.Alt(
                    gram.MatchToken('IDENT'),
                    gram.MatchGroup('keywords'),
                )
            )
        ),
        gram.Opt(
            gram.MatchKeyword('__inline__')
        ),
        gram.Opt(
            gram.MatchGroup('privacity'),
        ),
        gram.Opt(
            gram.MatchKeyword('__inline__')
        ),
        gram.Opt(
            gram.Ref(EGL_TYPE_SPEC)
        ),
        gram.Alt(
            gram.MatchToken('IDENT'),
            gram.MatchKeyword('__new__'),
            gram.MatchKeyword('__init__'),
            gram.MatchGroup('keywords'),
        ),
        gram.Ref(EGL_PARAMS),
        gram.Opt(
            gram.MatchToken('COMMENT')
        ),
        gram.Ref(EGL_FUNC_BODY),
    )

class EGL_CLASS_STMT(gram.RuleItem):
    name = "EGL_CLASS_STMT"
    code = gram.AutoCode()
    ignore = True
    grammar = gram.Alt(
        gram.Ref(EGL_METHOD_DECL),
        gram.Ref(EGL_VAR_DECL),
        gram.Ref(EGL_STATEMENT),
        gram.MatchKeyword('pass'),
        gram.MatchToken('COMMENT'),
    )

class EGL_CLASS_BODY(gram.RuleItem):
    name = "EGL_CLASS_BODY"
    code = gram.AutoCode()
    grammar = gram.Alt(
        gram.Seq(
            gram.MatchToken('COLON'),
            gram.MatchToken('INDENT'),
            gram.Some(
                gram.Ref(EGL_CLASS_STMT)
            ),
            gram.MatchToken('DEDENT')
        ),
        gram.Seq(
            gram.MatchToken('LBRACE'),
            gram.Opt(gram.MatchToken('INDENT')),
            gram.Some(
                gram.Ref(EGL_CLASS_STMT)
            ),
            gram.Opt(gram.MatchToken('DEDENT')),
            gram.MatchToken('RBRACE')
        )
    )

class EGL_CLASS_DECL(gram.RuleItem):
    name = "EGL_CLASS_DECL"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Opt(
            gram.MatchGroup('privacity')
        ),
        gram.Alt(
            gram.MatchKeyword('class'),
            gram.MatchKeyword('struct'),
        ),
        gram.Alt(
            gram.MatchToken('IDENT'),
            gram.MatchGroup('types'),
        ),
        gram.Ref(EGL_CLASS_BODY)
    )

__all__ = [
    'EGL_METHOD_DECL',
    'EGL_CLASS_STMT',
    'EGL_CLASS_BODY',
    'EGL_CLASS_DECL',
]

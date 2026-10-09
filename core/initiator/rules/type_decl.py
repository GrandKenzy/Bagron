import gram
from core.initiator.rules.value import EGL_VALUE
from core.initiator.rules.params import EGL_PARAMS
from core.initiator.rules.statement import EGL_STMT_BODY

class EGL_TYPE_SPEC(gram.RuleItem):
    name = "EGL_TYPE_SPEC"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Alt(
            gram.MatchGroup('types'),
            gram.MatchToken('IDENT'),
        ),
        gram.Opt(gram.MatchToken(gram.Token.STAR)),
        gram.Opt(
            gram.Enclosed(
                gram.Token.LBRACKET,
                gram.Separator(
                    sep=gram.Token.COMMA,
                    values=[
                        gram.Alt(
                            gram.MatchGroup('types'),
                            gram.MatchToken('IDENT'),
                            gram.MatchToken('NUMBER'),
                        )
                    ],
                    min=1
                ),
                gram.Token.RBRACKET
            )
        )
    )

class EGL_PASS(gram.RuleItem):
    name = "EGL_PASS"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('pass'),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

class EGL_TYPE_INIT(gram.RuleItem):
    name = "EGL_TYPE_INIT"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('__init__'),
        gram.Ref(EGL_TYPE_SPEC),
        gram.MatchToken('IDENT'),
        gram.Opt(
            gram.Seq(
                gram.MatchToken('ASSIGN'),
                gram.Ref(EGL_VALUE)
            )
        ),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

class EGL_TYPE_SETV(gram.RuleItem):
    name = "EGL_TYPE_SETV"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('__setv__'),
        gram.Ref(EGL_TYPE_SPEC),
        gram.MatchToken('IDENT'),
        gram.Opt(
            gram.Seq(
                gram.MatchToken('ASSIGN'),
                gram.Ref(EGL_VALUE)
            )
        ),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

class EGL_TYPE_MEMBER(gram.RuleItem):
    name = "EGL_TYPE_MEMBER"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('__member__'),
        gram.Opt(gram.Ref(EGL_TYPE_SPEC)),
        gram.MatchToken('IDENT'),
        gram.Ref(EGL_STMT_BODY)
    )

class EGL_TYPE_METHOD(gram.RuleItem):
    name = "EGL_TYPE_METHOD"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('__method__'),
        gram.Ref(EGL_TYPE_SPEC),
        gram.MatchToken('IDENT'),
        gram.Ref(EGL_PARAMS),
        gram.Ref(EGL_STMT_BODY)
    )

class EGL_TYPE_SPECIAL_METHOD(gram.RuleItem):
    name = "EGL_TYPE_SPECIAL_METHOD"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Ref(EGL_TYPE_SPEC),
        gram.MatchToken('IDENT'),
        gram.Ref(EGL_PARAMS),
        gram.Ref(EGL_STMT_BODY)
    )

class EGL_PTR_FIELD(gram.RuleItem):
    name = 'EGL_PTR_FIELD'
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('ptr'),
        gram.Alt(
            gram.MatchGroup('types'),
            gram.MatchToken('IDENT'),
        ),
        gram.MatchToken('IDENT'),
        gram.Opt(
            gram.Seq(
                gram.MatchToken('ASSIGN'),
                gram.Ref(EGL_VALUE)
            )
        ),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

class EGL_TYPE_FIELD(gram.RuleItem):
    name = "EGL_TYPE_FIELD"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Ref(EGL_TYPE_SPEC),
        gram.MatchToken('IDENT'),
        gram.Opt(
            gram.Seq(
                gram.MatchToken('ASSIGN'),
                gram.Ref(EGL_VALUE)
            )
        ),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

class EGL_TYPE_STMT(gram.RuleItem):
    name = "EGL_TYPE_STMT"
    code = gram.AutoCode()
    ignore = True
    grammar = gram.Alt(
        gram.Ref(EGL_TYPE_INIT),
        gram.Ref(EGL_TYPE_SETV),
        gram.Ref(EGL_TYPE_MEMBER),
        gram.Ref(EGL_TYPE_METHOD),
        gram.Ref(EGL_TYPE_SPECIAL_METHOD),
        gram.Ref(EGL_PTR_FIELD),
        gram.Ref(EGL_TYPE_FIELD),
        gram.Ref(EGL_PASS),
    )

class EGL_TYPE_BODY(gram.RuleItem):
    name = "EGL_TYPE_BODY"
    code = gram.AutoCode()
    grammar = gram.Alt(
        gram.Seq(
            gram.MatchToken('COLON'),
            gram.MatchToken('INDENT'),
            gram.Some(
                gram.Ref(EGL_TYPE_STMT)
            ),
            gram.MatchToken('DEDENT')
        ),
        gram.Seq(
            gram.MatchToken('LBRACE'),
            gram.Opt(gram.MatchToken('INDENT')),
            gram.Some(
                gram.Ref(EGL_TYPE_STMT)
            ),
            gram.Opt(gram.MatchToken('DEDENT')),
            gram.MatchToken('RBRACE')
        )
    )

class EGL_TYPE_DECL(gram.RuleItem):
    name = "EGL_TYPE_DECL"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Opt(
            gram.MatchGroup('privacity'),
        ),
        gram.MatchKeyword('type'),
        gram.Alt(
            gram.MatchToken('IDENT'),
            gram.MatchGroup('types'),
        ),
        gram.Ref(EGL_TYPE_BODY)
    )

__all__ = [
    'EGL_TYPE_SPEC',
    'EGL_TYPE_INIT',
    'EGL_TYPE_SETV',
    'EGL_TYPE_MEMBER',
    'EGL_TYPE_METHOD',
    'EGL_TYPE_SPECIAL_METHOD',
    'EGL_PTR_FIELD',
    'EGL_TYPE_FIELD',
    'EGL_PASS',
    'EGL_TYPE_STMT',
    'EGL_TYPE_BODY',
    'EGL_TYPE_DECL',
]

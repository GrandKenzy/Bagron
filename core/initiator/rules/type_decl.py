import gram
from core.initiator.rules.value import EGL_VALUE
from core.initiator.rules.params import EGL_PARAMS
from core.initiator.rules.statement import EGL_STMT_BODY, EGL_STATEMENT
from core.initiator.rules.type_spec import EGL_TYPE_SPEC

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
        gram.Opt(
            gram.Alt(
                gram.Seq(
                    gram.MatchToken('IDENT'),
                    gram.MatchToken('ASSIGN'),
                    gram.Ref(EGL_VALUE)
                ),
                gram.Ref(EGL_VALUE),
            )
        ),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

class EGL_TYPE_SLOT(gram.RuleItem):
    name = "EGL_TYPE_SLOT"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('__slot__'),
        gram.Ref(EGL_TYPE_SPEC),
        gram.Opt(gram.MatchToken('IDENT')),
        gram.Opt(
            gram.Seq(
                gram.MatchToken('ASSIGN'),
                gram.Ref(EGL_VALUE)
            )
        ),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

class EGL_TYPE_KIND(gram.RuleItem):
    name = "EGL_TYPE_KIND"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('__type__'),
        gram.Alt(
            gram.MatchToken('STRING'),
            gram.MatchToken('IDENT'),
        ),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

class EGL_TYPE_ITEMS(gram.RuleItem):
    name = "EGL_TYPE_ITEMS"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('__items__'),
        gram.MatchToken('COLON'),
        gram.Opt(gram.MatchToken('COMMENT')),
        gram.Alt(
            gram.Seq(
                gram.MatchToken('INDENT'),
                gram.Some(
                    gram.Seq(
                        gram.Ref(EGL_VALUE),
                        gram.Opt(gram.MatchToken('COMMA')),
                        gram.Opt(gram.MatchToken('COMMENT')),
                    )
                ),
                gram.MatchToken('DEDENT')
            ),
            gram.Seq(
                gram.Ref(EGL_VALUE),
                gram.Opt(gram.MatchToken('COMMENT'))
            )
        )
    )

class EGL_TYPE_DTYPE(gram.RuleItem):
    name = "EGL_TYPE_DTYPE"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('__dtype__'),
        gram.MatchToken('ASSIGN'),
        gram.Ref(EGL_VALUE),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

class EGL_TYPE_ACCESSOR(gram.RuleItem):
    name = "EGL_TYPE_ACCESSOR"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Opt(gram.Ref(EGL_TYPE_SPEC)),
        gram.Alt(
            gram.MatchKeyword('__getter__'),
            gram.MatchKeyword('__setter__'),
            gram.MatchKeyword('__getitem__'),
            gram.MatchKeyword('__setitem__'),
        ),
        gram.Ref(EGL_PARAMS),
        gram.Alt(
            gram.Ref(EGL_STMT_BODY),
            gram.Seq(
                gram.MatchToken('COLON'),
                gram.Ref(EGL_STATEMENT),
                gram.Opt(gram.MatchToken('COMMENT'))
            )
        )
    )

class EGL_TYPE_STMT(gram.RuleItem):
    name = "EGL_TYPE_STMT"
    code = gram.AutoCode()
    ignore = True
    grammar = gram.Alt(
        gram.Ref(EGL_TYPE_SLOT),
        gram.Ref(EGL_TYPE_KIND),
        gram.Ref(EGL_TYPE_ITEMS),
        gram.Ref(EGL_TYPE_DTYPE),
        gram.Ref(EGL_TYPE_ACCESSOR),
        gram.Ref(EGL_TYPE_INIT),
        gram.Ref(EGL_TYPE_SETV),
        gram.Ref(EGL_TYPE_MEMBER),
        gram.Ref(EGL_TYPE_METHOD),
        gram.Ref(EGL_TYPE_SPECIAL_METHOD),
        gram.Ref(EGL_PTR_FIELD),
        gram.Ref(EGL_TYPE_FIELD),
        gram.Ref(EGL_PASS),
        gram.MatchToken('COMMENT'),
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
        gram.Alt(
            gram.Seq(
                gram.MatchKeyword('struct'),
                gram.MatchKeyword('Type'),
            ),
            gram.MatchKeyword('Type'),
            gram.MatchKeyword('type'),
            gram.MatchKeyword('enum'),
        ),
        gram.Alt(
            gram.MatchToken('IDENT'),
            gram.MatchGroup('types'),
        ),
        gram.Ref(EGL_TYPE_BODY)
    )

__all__ = [
    'EGL_TYPE_SPEC',
    'EGL_TYPE_SLOT',
    'EGL_TYPE_KIND',
    'EGL_TYPE_ITEMS',
    'EGL_TYPE_DTYPE',
    'EGL_TYPE_ACCESSOR',
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

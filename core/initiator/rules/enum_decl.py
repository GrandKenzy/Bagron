import gram

class EGL_ENUM_VALUE(gram.RuleItem):
    name = "EGL_ENUM_VALUE"
    code = gram.AutoCode()
    grammar = gram.Alt(
        gram.Seq(
            gram.Opt(gram.MatchToken('MINUS')),
            gram.MatchToken('NUMBER')
        ),
        gram.MatchToken('IDENT'),
        gram.MatchToken('STRING')
    )

class EGL_ENUM_ITEM(gram.RuleItem):
    name = "EGL_ENUM_ITEM"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchToken('IDENT'),
        gram.Opt(
            gram.Seq(
                gram.MatchToken('ASSIGN'),
                gram.Ref(EGL_ENUM_VALUE)
            )
        ),
        gram.Opt(gram.MatchToken('COMMA')),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

class EGL_ENUM_STMT(gram.RuleItem):
    name = "EGL_ENUM_STMT"
    code = gram.AutoCode()
    ignore = True
    grammar = gram.Alt(
        gram.Ref(EGL_ENUM_ITEM),
        gram.MatchKeyword('pass'),
        gram.MatchToken('COMMENT'),
    )

class EGL_ENUM_BODY(gram.RuleItem):
    name = "EGL_ENUM_BODY"
    code = gram.AutoCode()
    grammar = gram.Alt(
        gram.Seq(
            gram.MatchToken('COLON'),
            gram.MatchToken('INDENT'),
            gram.Some(gram.Ref(EGL_ENUM_STMT)),
            gram.MatchToken('DEDENT')
        ),
        gram.Seq(
            gram.MatchToken('COLON'),
            gram.Some(gram.Ref(EGL_ENUM_STMT))
        ),
        gram.Seq(
            gram.MatchToken('LBRACE'),
            gram.Opt(gram.MatchToken('INDENT')),
            gram.Some(gram.Ref(EGL_ENUM_STMT)),
            gram.Opt(gram.MatchToken('DEDENT')),
            gram.MatchToken('RBRACE')
        )
    )

class EGL_ENUM_DECL(gram.RuleItem):
    name = "EGL_ENUM_DECL"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Opt(gram.MatchGroup('privacity')),
        gram.MatchKeyword('enum'),
        gram.MatchToken('IDENT'),
        gram.Ref(EGL_ENUM_BODY)
    )

__all__ = [
    'EGL_ENUM_VALUE',
    'EGL_ENUM_ITEM',
    'EGL_ENUM_STMT',
    'EGL_ENUM_BODY',
    'EGL_ENUM_DECL',
]

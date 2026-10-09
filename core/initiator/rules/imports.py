import gram

class EGL_IMPORT(gram.RuleItem):
    name = "EGL_IMPORT"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('import'),
        gram.Alt(
            gram.MatchToken('IDENT'),
            gram.MatchToken('STRING'),
        ),
        gram.Opt(
            gram.Seq(
                gram.MatchKeyword('as'),
                gram.MatchToken('IDENT')
            )
        )
    )

class EGL_INCLUDE(gram.RuleItem):
    name = "EGL_INCLUDE"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('include'),
        gram.Alt(
            gram.MatchToken('IDENT'),
            gram.MatchToken('STRING'),
        ),
        gram.Opt(
            gram.Seq(
                gram.MatchKeyword('as'),
                gram.MatchToken('IDENT')
            )
        )
    )

class EGL_CLASS(gram.RuleItem):
    name = "EGL_CLASS"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('class'),
        gram.MatchToken('IDENT'),
        gram.Opt(
            gram.Seq(
                gram.MatchKeyword('as'),
                gram.MatchToken('IDENT')
            )
        )
    )
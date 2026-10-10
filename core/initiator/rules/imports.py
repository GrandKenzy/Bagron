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

class EGL_OBJECT(gram.RuleItem):
    name = "EGL_OBJECT"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('object'),
        gram.MatchToken('IDENT'),
        gram.Opt(
            gram.Seq(
                gram.MatchKeyword('as'),
                gram.MatchToken('IDENT')
            )
        )
    )

class EGL_DECLARE(gram.RuleItem):
    name = "EGL_DECLARE"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('declare'),
        gram.Alt(
            gram.Seq(
                gram.MatchToken('IDENT'),
                gram.MatchToken(gram.Token.DOT),
                gram.MatchToken('IDENT'),
            ),
            gram.MatchToken('IDENT'),
        ),
        gram.MatchKeyword('as'),
        gram.MatchToken('IDENT'),
        gram.Opt(gram.MatchToken('COMMENT'))
    )

__all__ = [
    'EGL_IMPORT',
    'EGL_INCLUDE',
    'EGL_OBJECT',
    'EGL_DECLARE',
]
import gram

class EGL_TYPE_SPEC(gram.RuleItem):
    name = "EGL_TYPE_SPEC"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.Alt(
            gram.Seq(
                gram.MatchKeyword('__void_p_t__'),
                gram.MatchGroup('types')
            ),
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

__all__ = ['EGL_TYPE_SPEC']

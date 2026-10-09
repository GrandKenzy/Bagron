import gram

class EGL_VALUE(gram.RuleItem):
    name = 'EGL_VALUE'
    code = gram.AutoCode()
    grammar = gram.Alt(
        gram.MatchToken('NUMBER'),
        gram.MatchToken('IDENT'),
        gram.MatchToken('STRING'),
    )

EC_VALUE = EGL_VALUE

import gram

class EGL_CLAUSE(gram.RuleItem):
    name = "EGL_CLAUSE"
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('clause'),
        gram.MatchGroup('clauses'),
        gram.Alt(
            gram.MatchToken('STRING'),
            gram.MatchToken('NUMBER')
        )
    )
import gram


class EC_VALUE(gram.RuleItem):
    name='Value'
    code=100_001
    grammar=gram.Alt(
        gram.MatchToken('NUMBER'),
        gram.MatchToken('IDENT'),
        gram.MatchToken('STRING'),
    )
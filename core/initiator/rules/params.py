import gram

class EC_PARAM(gram.RuleItem):
    name = 'ec_param'
    code = 100_004
    grammar = gram.Seq(
        gram.MatchGroup('types'),
        gram.MatchToken('IDENT'),
    )
    
class EC_PARAMS(gram.RuleItem):
    name = 'ec_params'
    code = 100_005
    grammar = gram.Enclosed(
        open=gram.Token.LPAREN,
        content=gram.Opt(
                gram.Alt(
                        gram.Separator(
                            sep=gram.Token.COMMA,
                            values=[
                                gram.Ref(EC_PARAM)
                            ]
                        ),
                        gram.MatchKeyword('void')
                    ),
            ),
        close=gram.Token.RPAREN
    )
import gram
from core.initiator.rules.params import EC_PARAMS
from core.initiator.rules.var_decl import EC_VAR_DECL, EC_VALUE

class EC_RETURN(gram.RuleItem):
    name = 'return'
    code = 100_005
    grammar = gram.Seq(
        gram.MatchKeyword('return'),
        gram.Ref(EC_VALUE)
    )

class EC_FUNC_BODY(gram.RuleItem):
    name = 'func body'
    code = 100_006
    grammar = gram.Seq(
        gram.MatchToken('COLON'),
        gram.MatchToken('INDENT'),
        gram.Some(
            gram.Alt(
                gram.Ref(EC_RETURN),
                gram.Ref(EC_VAR_DECL),
            ),
        ),
        gram.MatchToken('DEDENT')
    )
    
# class EC_FUNC_BODY(gram.RuleItem):
#     name = 'func body'
#     code = 100_007
#     grammar = gram.Enclosed(
#         open=gram.Token.LBRACE,
#         content=gram.Some(
#             gram.Alt(
#                 gram.Ref(EC_VAR_DECL),
#                 gram.Ref(EC_RETURN)
#             )
#         ),
#         close=gram.Token.RBRACE
#     )
        


class EC_FUNC_DECL(gram.RuleItem):
    name = 'func declaration'
    code = 100_003
    grammar = gram.Seq(
        gram.Opt(
            gram.MatchGroup('privacity'),
        ),
        gram.MatchGroup('types'),
        gram.MatchToken('IDENT'),
        gram.Ref(EC_PARAMS),
        gram.Opt(
            gram.MatchToken('COMMENT')
        ),
        gram.Alt(
            gram.Ref(EC_FUNC_BODY),
        )
    )
import core, gram

class EC_DECLARATION(gram.RuleItem):
    code = 100_002
    name = 'DECLARATION'
    grammar = gram.Alt(
        gram.Ref(core.initiator.EC_VAR_DECL)
    )


grammar = {
    gram.PROGRAM: gram.Many(
        gram.Ref(EC_DECLARATION)
    )
}
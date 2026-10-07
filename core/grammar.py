
import core, gram
from core.initiator import rules


grammar = {
    gram.PROGRAM: gram.Many(
        gram.Ref(gram.DECLARATION)
    ),
    gram.DECLARATION: gram.Alt(
        gram.Ref(rules.EC_VAR_DECL),
        gram.Ref(rules.EC_FUNC_DECL)
    )
}
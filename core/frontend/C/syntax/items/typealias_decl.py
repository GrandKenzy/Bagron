from gram import combinators as cmb

from core.frontend.C.syntax.items.value import POINTER, QUALIFIER, TYPE


class TYPEDEF(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('typedef'),
        cmb.Opt(cmb.Alt(
            cmb.MatchKeyword('struct'),
            cmb.MatchKeyword('union'),
            cmb.MatchKeyword('enum')
        )),
        cmb.Opt(cmb.Ref(QUALIFIER)),
        cmb.Ref(TYPE),
        cmb.Opt(cmb.Ref(POINTER)),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('SEMICOLON')
    )


__all__ = [
    'TYPEDEF',
]

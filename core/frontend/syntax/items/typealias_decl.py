from gram import combinators as cmb

from core.frontend.syntax.items.value import TYPE


class TYPEALIAS(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.MatchKeyword('TypeAlias'),
        cmb.Ref(TYPE),
        cmb.MatchToken('IDENT'),
    )
    nodeable = True



__all__ = [
    'TYPE',
]
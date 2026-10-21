from gram import combinators as cmb
from core.initiator.rules.value import SEGMENT_TYPE


class TYPEALIAS(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.MatchKeyword('TypeAlias'),
        cmb.Ref(SEGMENT_TYPE),
        cmb.MatchToken('IDENT'),
    )
    nodeable = True


TYPE = TYPEALIAS

__all__ = [
    'TYPEALIAS',
    'TYPE',
]
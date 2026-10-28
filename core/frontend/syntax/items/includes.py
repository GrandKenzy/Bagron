from gram import combinators as cmb


class INCLUDE(cmb.RuleItem):
    """Native header and library declaration."""

    entrypoint = cmb.Seq(
        cmb.MatchKeyword('include'),
        cmb.MatchToken('STRING'),
        cmb.MatchKeyword('link'),
        cmb.MatchToken('STRING'),
    )
    nodeable = True


__all__ = ['INCLUDE']

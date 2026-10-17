from gram import combinators as cmb


class CLAUSE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('clause'),
        cmb.MatchGroup('clauses'),
        cmb.Alt(
            cmb.MatchToken('STRING'),
            cmb.MatchToken('NUMBER'),
            cmb.MatchToken('BOOL')
        )
    )
    nodeable = True


__all__ = [
    'CLAUSE',
]
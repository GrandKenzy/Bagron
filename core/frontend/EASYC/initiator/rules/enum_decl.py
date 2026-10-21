from gram import combinators as cmb


class ENUM_VALUE(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Seq(
            cmb.Opt(cmb.MatchToken('MINUS')),
            cmb.MatchToken('NUMBER'),
        ),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('STRING'),
    )
    nodeable = True


class ENUM_ITEM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Opt(
            cmb.Seq(
                cmb.MatchToken('ASSIGN'),
                cmb.Ref(ENUM_VALUE),
            )
        ),
        cmb.Opt(cmb.MatchToken('COMMA')),
    )
    nodeable = True


class ENUM_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(ENUM_ITEM),
                cmb.MatchKeyword('pass'),
            )
        ),
        cmb.MatchToken('DEDENT'),
    )
    nodeable = True


class ENUM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.MatchKeyword('enum'),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('COLON'),
        cmb.Ref(ENUM_BODY),
    )
    nodeable = True


__all__ = [
    'ENUM',
    'ENUM_ITEM',
    'ENUM_VALUE',
    'ENUM_BODY',
]

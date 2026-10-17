from gram import combinators as cmb

from core.initiator.rules.value import SEGMENT_TYPE


class BITFIELD_ITEM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(SEGMENT_TYPE),
        cmb.Opt(cmb.MatchToken('IDENT')),  # Puede ser anónimo para padding de bits (ej: uint8 : 2)
        cmb.MatchToken('COLON'),
        cmb.MatchToken('NUMBER'),
    )
    nodeable = True


class FLAGS_FIRM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.Opt(cmb.MatchKeyword('__volatile__')),
        cmb.MatchKeyword('flags'),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('COLON'),
    )
    nodeable = True


class FLAGS_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(BITFIELD_ITEM),
                cmb.MatchKeyword('pass'),
            )
        ),
        cmb.MatchToken('DEDENT'),
    )
    nodeable = True


class FLAGS(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(FLAGS_FIRM),
        cmb.Ref(FLAGS_BODY),
    )
    nodeable = True


__all__ = [
    'BITFIELD_ITEM',
    'FLAGS_FIRM',
    'FLAGS_BODY',
    'FLAGS',
]

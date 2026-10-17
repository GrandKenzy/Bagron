from gram import combinators as cmb

from core.initiator.rules.flags_decl import BITFIELD_ITEM
from core.initiator.rules.var_decl import VAR_PARTIAL_DECL, VAR_PTR_GENERIC_PARTIAL


class STRUCT_PACKED(cmb.RuleItem):
    entrypoint = cmb.MatchKeyword('__packed__')
    nodeable = True


class STRUCT_ALIGN(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('__align__'),
        cmb.Opt(
            cmb.Alt(
                cmb.MatchToken('NUMBER'),
                cmb.MatchGroup('types'),
            )
        ),
    )
    nodeable = True


class STRUCT_FIRM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.Opt(cmb.MatchKeyword('__volatile__')),
        cmb.MatchKeyword('struct'),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('COLON'),
    )
    nodeable = True


class STRUCT_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('INDENT'),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(BITFIELD_ITEM),     # pointer tipo nombre : bits
                cmb.Ref(VAR_PARTIAL_DECL),  # x: int
                cmb.Ref(VAR_PTR_GENERIC_PARTIAL),  # ptr p
                cmb.Ref(STRUCT_PACKED),     # __packed__
                cmb.Ref(STRUCT_ALIGN),      # __align__ [NUMBER | tipo]
                cmb.MatchKeyword('pass'),
            )
        ),
        cmb.MatchToken('DEDENT'),
    )
    nodeable = True


class STRUCT(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(STRUCT_FIRM),
        cmb.Ref(STRUCT_BODY),
    )
    nodeable = True


__all__ = [
    'STRUCT_PACKED',
    'STRUCT_ALIGN',
    'STRUCT_FIRM',
    'STRUCT_BODY',
    'STRUCT',
]

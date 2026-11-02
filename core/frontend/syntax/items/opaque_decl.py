from gram import combinators as cmb

from core.frontend.syntax.items.value import POINTER, TYPE


class OPAQUE_SIGNATURE(cmb.RuleItem):
    """Nominal descriptor name followed by its compiler-known ABI shape."""

    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.MatchKeyword('opaque'),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('COLON'),
        cmb.Ref(TYPE),
        cmb.Opt(cmb.Ref(POINTER)),
    )
    nodeable = True


class OPAQUE(cmb.RuleItem):
    entrypoint = cmb.Ref(OPAQUE_SIGNATURE)
    nodeable = True


__all__ = ['OPAQUE', 'OPAQUE_SIGNATURE']

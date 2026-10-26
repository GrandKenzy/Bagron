from gram import combinators as cmb

from core.frontend.syntax.items.value import (
    CALL_SUFFIX,
    INDEX_ACCESS,
    MEMBER_ACCESS,
    PRIMARY,
)


class CALL(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Ref(PRIMARY),
        cmb.Many(
            cmb.Alt(
                cmb.Ref(MEMBER_ACCESS),
                cmb.Ref(INDEX_ACCESS),
            )
        ),
        cmb.Ref(CALL_SUFFIX),
        cmb.Many(
            cmb.Alt(
                cmb.Ref(CALL_SUFFIX),
                cmb.Ref(MEMBER_ACCESS),
                cmb.Ref(INDEX_ACCESS),
            )
        ),
    )
    
__all__ = ['CALL']

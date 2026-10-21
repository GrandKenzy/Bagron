from gram import combinators as cmb
from gram import lexer

from core.initiator.rules.call import MEMBER_CHAIN
from core.initiator.rules.value import ALIAS


class IMPORT_SPEC(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Opt(cmb.Ref(ALIAS)),
    )
    nodeable = True


class IMPORT_GROUP(cmb.RuleItem):
    entrypoint = cmb.Enclosed(
        open=lexer.Token.LBRACE,
        close=lexer.Token.RBRACE,
        content=cmb.Separator(
            values=cmb.Ref(IMPORT_SPEC),
            sep=lexer.Token.COMMA,
            min=1,
            allow_trailing=True,
        ),
    )
    nodeable = True


class IMPORT(cmb.RuleItem):
    entrypoint = cmb.Alt(
        # import { a, b as B } from modulo
        cmb.Seq(
            cmb.MatchKeyword('import'),
            cmb.Ref(IMPORT_GROUP),
            cmb.MatchKeyword('from'),
            cmb.MatchToken('IDENT'),
        ),
        # import modulo [as alias]
        cmb.Seq(
            cmb.MatchKeyword('import'),
            cmb.MatchToken('IDENT'),
            cmb.Opt(cmb.Ref(ALIAS)),
        ),
    )
    nodeable = True


class INCLUDE(cmb.RuleItem):
    entrypoint = cmb.Alt(
        # include { a, b as B } from "header.h"
        cmb.Seq(
            cmb.MatchKeyword('include'),
            cmb.Ref(IMPORT_GROUP),
            cmb.MatchKeyword('from'),
            cmb.MatchToken('STRING'),
        ),
        # include "header.h" [as alias]
        cmb.Seq(
            cmb.MatchKeyword('include'),
            cmb.MatchToken('STRING'),
            cmb.Opt(cmb.Ref(ALIAS)),
        ),
    )
    nodeable = True


class OBJECT(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('object'),
        cmb.MatchToken('IDENT'),
        cmb.Opt(cmb.Ref(ALIAS)),
    )
    nodeable = True


__all__ = [
    'IMPORT',
    'IMPORT_SPEC',
    'IMPORT_GROUP',
    'INCLUDE',
    'OBJECT',
]
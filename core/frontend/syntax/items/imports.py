from gram import combinators as cmb
from gram import lexer

from core.frontend.syntax.items.value import ALIAS


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


__all__ = [
    'IMPORT',
]

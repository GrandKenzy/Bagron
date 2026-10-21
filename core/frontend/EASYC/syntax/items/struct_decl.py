from gram import combinators as cmb

from core.frontend.EASYC.syntax.items.var_decl import VAR_INITIALIZATION


class ALIGNEMENT(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword('__align__'),
        cmb.Alt(
            cmb.MatchToken('NUMBER'),
            cmb.MatchGroup('types')
        )
    )
    nodeable = True
    
class ATTRIBUTES(cmb.RuleItem):
    entrypoint = cmb.Some(
        cmb.Alt(
            cmb.Ref(ALIGNEMENT),
            cmb.MatchKeyword('__packed__'),
        )
    )
    nodeable = True
    
class STRUCT_SIGNATURE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.Opt(cmb.MatchKeyword('volatile')),
        cmb.MatchKeyword('struct'),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('COLON')
    )
    nodeable = True
    
class FLAGS_SIGNATURE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.Opt(cmb.MatchKeyword('volatile')),
        cmb.MatchKeyword('flags'),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('COLON')
    )
    nodeable = True
    
class MOLD_SIGNATURE(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Opt(cmb.MatchGroup('privacy')),
        cmb.Opt(cmb.MatchKeyword('volatile')),
        cmb.MatchKeyword('mold'),
        cmb.MatchToken('IDENT'),
        cmb.MatchToken('COLON')
    )
    nodeable = True
    
    
class STRUCT_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Opt(cmb.Ref(ATTRIBUTES)),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(VAR_INITIALIZATION),
                cmb.MatchKeyword('pass')
            )
        )
    )
    nodeable = True
    

class FLAG_VAR(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(VAR_INITIALIZATION),
        cmb.MatchToken('UNDERSCORE'),
        cmb.MatchToken('NUMBER')
    )
    nodeable = True
    
class FLAGS_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Opt(cmb.Ref(ATTRIBUTES)),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(FLAG_VAR),
                cmb.MatchKeyword('pass')
            )
        )
    )
    nodeable = True 
    
   
class MOLD_BODY(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken('IDENT'),
        cmb.Opt(cmb.Ref(ATTRIBUTES)),
        cmb.Some(
            cmb.Alt(
                cmb.Ref(VAR_INITIALIZATION),
                cmb.MatchKeyword('pass')
            )
        )
    )
    nodeable = True
    

class STRUCT(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(STRUCT_SIGNATURE),
        cmb.Ref(STRUCT_BODY),
    )
    nodeable = True
class FLAGS(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(FLAGS_SIGNATURE),
        cmb.Ref(FLAGS_BODY),
    )
    nodeable = True
class MOLD(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(MOLD_SIGNATURE),
        cmb.Ref(MOLD_BODY),
    )
    nodeable = True

__all__ = [
    'FLAGS',
    'MOLD',
    'STRUCT'
]
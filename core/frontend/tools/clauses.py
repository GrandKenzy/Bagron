import platform

from gram import ast as gast

from core import globvars


def _visibility(var: str): return var in ('public', 'private')
def _architecture(var: str):
    return var in ('auto', 'amd', 'arm', 'x86') or '-' in str(var)
def _optimizations(var: str): return var in ('dev', 'prod', 'high')
def _stack_limit(var: str | int): return isinstance(var, int)

def _system(var: str):
    if var == 'auto':
        var = platform.system().lower()
    return var in ('linux', 'windows')


def validate(clause: gast.ASTRef):
    clause_name = clause.nodes[1].token.value # type: ignore
    clause_value = clause.nodes[2].token.value # type: ignore
    
    if clause_name not in globvars.CLAUSES:
        raise ValueError(f'La clausula {clause_name!r} no existe')
        
    if clause_name == 'Visibility' and _visibility(clause_value):  # noqa: SIM114
        pass
    elif clause_name == 'Arch' and _architecture(clause_value):  # noqa: SIM114
        pass
    elif clause_name == 'System' and _system(clause_value):  # noqa: SIM114
        pass
    elif clause_name == 'Optimizations' and _optimizations(clause_value):  # noqa: SIM114
        pass
    elif clause_name == 'StackLimit' and _stack_limit(clause_value):
        pass
    else:
        raise ValueError(
            f'La clausula {clause_name!r} posee un valor invalido: {clause_value!r}'
        )
    
    return clause_name, clause_value

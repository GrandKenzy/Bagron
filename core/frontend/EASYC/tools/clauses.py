import platform

from gram import ast as gast

from core import globvars


def _visibility(var: str): return var in ('public', 'private')
def _architecture(var: str): return var in ('amd', 'arm', 'x86')
def _optimizations(var: str): return var in ('dev', 'prod', 'high')
def _stack_limit(var: str | int): return isinstance(var, int)

def _system(var: str):
    if var == 'auto':
        var = platform.system().lower()
    return var in ('linux', 'windows')


def validate(clause: gast.ASTRef):
    clause_name = clause.nodes[1].token.value # type: ignore
    clause_value = clause.nodes[2].token.value # type: ignore
    
    if not clause_name in globvars.CLAUSES:
        print('La clausula', clause_name, 'no existe')
        # temp
        
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
        print('La clausula', clause_name, 'posee un valor inválido:', clause_value)
    
    return clause_name, clause_value
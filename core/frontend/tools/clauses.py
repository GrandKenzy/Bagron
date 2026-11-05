from gram import ast as gast

from core import globvars
from core.compiler.platforms import (
    validate_architecture_option,
    validate_system_option,
)


def _visibility(var: str): return var in ('public', 'private')
def _optimizations(var: str): return var in ('dev', 'prod', 'high')
def _stack_limit(var: str | int): return isinstance(var, int)
def _boot(var: str):
    return str(var).strip().lower() in {
        'none',
        'multiboot2',
        'uefi',
        'opensbi',
        'dtb',
        'custom',
    }

def _abi(var: str):
    return str(var).strip().lower() == 'sysv_amd64'

def validate(clause: gast.ASTRef):
    clause_name = clause.nodes[1].token.value # type: ignore
    clause_value = clause.nodes[2].token.value # type: ignore
    
    if clause_name not in globvars.CLAUSES:
        raise ValueError(f'La clausula {clause_name!r} no existe')
        
    if clause_name == 'Privacy' and _visibility(clause_value):  # noqa: SIM114
        pass
    elif clause_name == 'Arch':
        validate_architecture_option(clause_value)
    elif clause_name == 'System':
        validate_system_option(clause_value)
    elif clause_name == 'Boot' and _boot(clause_value):  # noqa: SIM114
        pass
    elif clause_name == 'ABI' and _abi(clause_value):  # noqa: SIM114
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

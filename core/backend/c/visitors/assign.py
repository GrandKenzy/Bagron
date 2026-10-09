from core.processor.objects import Assign, Function
from core.backend.c.visitors.variable import resolve_variable

def visit(assign: Assign, block: Function | None = None):
    target_str = str(assign.target.value if hasattr(assign.target, 'value') else assign.target)
    resolved = resolve_variable(target_str, block)
    val_str = str(assign.value.value if hasattr(assign.value, 'value') else assign.value)
    
    if resolved:
        resolved.uses += 1
        if resolved.is_pointer:
            val_resolved = resolve_variable(val_str, block)
            if val_resolved and val_resolved.is_pointer:
                assign.compiled = f'{resolved.name} = {val_resolved.name};'
            else:
                assign.compiled = f'*{resolved.name} = {val_str};'
            return
        assign.compiled = f'{resolved.name} = {val_str};'
        return
    assign.compiled = f'{target_str} = {val_str};'

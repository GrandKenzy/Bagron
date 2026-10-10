from core.processor.objects import Assign, Function
from core.backend.c.visitors.variable import resolve_variable

def visit(assign: Assign, block: Function | None = None):
    target_str = str(assign.target.value if hasattr(assign.target, 'value') else assign.target)
    val_str = str(assign.value.value if hasattr(assign.value, 'value') else assign.value)

    from core.backend.c.visitors.variable import convert_type, resolve_variable
    from core.backend.c.visitors.expression import format_expression
    fmt_val = format_expression(assign.value, block)

    if '[' in target_str and target_str.endswith(']'):
        base_name, idx_part = target_str[:-1].split('[', 1)
        base_resolved = resolve_variable(base_name.strip(), block)
        if base_resolved:
            base_resolved.uses += 1
            elem_t = convert_type(getattr(base_resolved, 'element_type', None) or 'int')
            if elem_t == 'char' and len(val_str.strip("'\"")) == 1:
                fmt_val = f"'{val_str.strip('\'\"')}'"
            assign.compiled = f'{base_resolved.name}[{idx_part}] = {fmt_val};'
            return

    resolved = resolve_variable(target_str, block)
    if resolved:
        resolved.uses += 1
        if resolved.is_pointer:
            val_resolved = resolve_variable(val_str, block)
            if fmt_val == 'NULL' or fmt_val.startswith('&') or resolved.type == 'ptr' or (val_resolved and val_resolved.is_pointer):
                assign.compiled = f'{resolved.name} = {fmt_val};'
            else:
                assign.compiled = f'*{resolved.name} = {fmt_val};'
            return
        assign.compiled = f'{resolved.name} = {fmt_val};'
        return
    if target_str.startswith(('self.', 'this.')):
        arrow_target = target_str.replace('self.', 'self->').replace('this.', 'this->')
        assign.compiled = f'{arrow_target} = {fmt_val};'
        return
    assign.compiled = f'{target_str} = {fmt_val};'

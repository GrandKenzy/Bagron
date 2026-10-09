from core.processor.objects import IfStatement, ForStatement, Call, Assign, Variable, Function
from core.backend.c.deffunc import deffunc
from core.backend.c.visitors import variable, assign
from core.backend.c.visitors.variable import resolve_variable

def _compile_condition(condition: any, block: Function | None = None) -> str:
    if isinstance(condition, (list, tuple)):
        if len(condition) == 2 and str(condition[0]) == 'not':
            var_target = str(condition[1].value if hasattr(condition[1], 'value') else condition[1])
            resolved = resolve_variable(var_target, block)
            if resolved:
                resolved.uses += 1
                return f'!{resolved.name}'
            return f'!{var_target}'
        parts = []
        for p in condition:
            val = str(p.value if hasattr(p, 'value') else p)
            if val == 'not':
                parts.append('!')
            else:
                resolved = resolve_variable(val, block)
                if resolved:
                    resolved.uses += 1
                    parts.append(resolved.name)
                else:
                    parts.append(val)
        return ' '.join(parts)
    cond_str = str(condition.value if hasattr(condition, 'value') else condition)
    resolved = resolve_variable(cond_str, block)
    if resolved:
        resolved.uses += 1
        return resolved.name
    return cond_str

def _compile_block(stmts: list, block: Function | None = None) -> list[str]:
    lines = []
    for item in stmts:
        if isinstance(item, Call):
            call_res = deffunc(item.name, item.args, getattr(item, 'kwargs', {}), is_statement=True, block=block)
            item.compiled = call_res.compiled
            lines.append(f'    {item.compiled}')
        elif isinstance(item, Assign):
            assign.visit(item, block)
            lines.append(f'    {item.compiled}')
        elif isinstance(item, Variable):
            variable.visit(item, block)
            lines.append(f'    {item.compiled}')
        elif isinstance(item, IfStatement):
            visit(item, block)
            for sub_l in item.compiled.split('\n'):
                lines.append(f'    {sub_l}')
        elif isinstance(item, ForStatement):
            from core.backend.c.visitors import for_statement
            for_statement.visit(item, block)
            for sub_l in item.compiled.split('\n'):
                lines.append(f'    {sub_l}')
    return lines

def visit(stmt: IfStatement, block: Function | None = None):
    cond_c = _compile_condition(stmt.condition, block)
    body_lines = _compile_block(stmt.body, block)
    body_str = '\n'.join(body_lines)
    if stmt.else_body:
        else_lines = _compile_block(stmt.else_body, block)
        else_str = '\n'.join(else_lines)
        stmt.compiled = f'if ({cond_c}) {{\n{body_str}\n}} else {{\n{else_str}\n}}'
    else:
        stmt.compiled = f'if ({cond_c}) {{\n{body_str}\n}}'

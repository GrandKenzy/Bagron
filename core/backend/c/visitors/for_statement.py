from typing import Any
from core.processor.objects import ForStatement, IfStatement, Call, Assign, Variable, Function
from core.backend.c.deffunc import deffunc
from core.backend.c.visitors import variable, assign
from core.backend.c.visitors.variable import resolve_variable

def _format_expr(expr_vals: Any, block: Function | None = None) -> str:
    if not isinstance(expr_vals, (list, tuple)):
        expr_vals = [expr_vals]
    parts = []
    for p in expr_vals:
        val = str(p.value if hasattr(p, 'value') else p)
        resolved = resolve_variable(val, block)
        if resolved:
            resolved.uses += 1
            parts.append(resolved.name)
        else:
            parts.append(val)
    if len(parts) >= 2 and parts[0] == 'this':
        return f'{parts[0]}.{parts[1]}'
    return ' '.join(parts)

def _compile_block(stmts: list, block: Function | None = None) -> list[str]:
    from core.backend.c.visitors import if_statement
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
            if_statement.visit(item, block)
            for sub_l in item.compiled.split('\n'):
                lines.append(f'    {sub_l}')
        elif isinstance(item, ForStatement):
            visit(item, block)
            for sub_l in item.compiled.split('\n'):
                lines.append(f'    {sub_l}')
    return lines

def visit(stmt: ForStatement, block: Function | None = None):
    var_name = stmt.var_name
    body_lines = _compile_block(stmt.body, block)
    body_str = '\n'.join(body_lines)
    
    if stmt.mode in ('ran', 'rand'):
        if isinstance(stmt.target, list) and len(stmt.target) == 2 and isinstance(stmt.target[0], list):
            start_val = _format_expr(stmt.target[0], block)
            limit_val = _format_expr(stmt.target[1], block)
        else:
            start_val = '0'
            limit_val = _format_expr(stmt.target, block)
        inc_line = f'    {var_name}++;'
        inner_body = f'{body_str}\n{inc_line}' if body_str else inc_line
        stmt.compiled = f'int {var_name} = {start_val};\nwhile ({var_name} < {limit_val}) {{\n{inner_body}\n}}'
    else:
        target_str = _format_expr(stmt.target, block)
        iter_var = f'_iter_{var_name}'
        inc_line = f'    {iter_var}++;'
        inner_body = f'{body_str}\n{inc_line}' if body_str else inc_line
        stmt.compiled = f'int {iter_var} = 0;\nwhile ({iter_var} < {target_str}.size) {{\n{inner_body}\n}}'

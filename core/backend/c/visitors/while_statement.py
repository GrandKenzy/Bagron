from typing import Any
from core.processor.objects import WhileStatement, ForStatement, IfStatement, Call, MethodCall, Assign, Variable, Function
from core.backend.c.deffunc import deffunc
from core.backend.c.visitors import variable, assign
from core.backend.c.visitors.variable import resolve_variable

def _compile_condition(condition: Any, block: Function | None = None) -> str:
    from core.backend.c.visitors.if_statement import _compile_condition as if_compile_cond
    return if_compile_cond(condition, block)

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
        elif isinstance(item, MethodCall):
            from core.backend.c.visitors import method_call
            method_call.visit(item, is_statement=True, block=block)
            lines.append(f'    {item.compiled}')
        elif isinstance(item, Variable):
            variable.visit(item, block)
            lines.append(f'    {item.compiled}')
        elif isinstance(item, IfStatement):
            if_statement.visit(item, block)
            for sub_l in item.compiled.split('\n'):
                lines.append(f'    {sub_l}')
        elif isinstance(item, ForStatement):
            from core.backend.c.visitors import for_statement
            for_statement.visit(item, block)
            for sub_l in item.compiled.split('\n'):
                lines.append(f'    {sub_l}')
        elif isinstance(item, WhileStatement):
            visit(item, block)
            for sub_l in item.compiled.split('\n'):
                lines.append(f'    {sub_l}')
    return lines

def visit(stmt: WhileStatement, block: Function | None = None):
    cond_str = _compile_condition(stmt.condition, block)
    body_lines = _compile_block(stmt.body, block)
    body_str = '\n'.join(body_lines)
    if body_str:
        stmt.compiled = f'while ({cond_str}) {{\n{body_str}\n}}'
    else:
        stmt.compiled = f'while ({cond_str}) {{\n}}'

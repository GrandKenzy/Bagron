from core.processor.objects import IfStatement, ForStatement, Call, Assign, Variable, Function, MethodCall
from core.backend.c.deffunc import deffunc
from core.backend.c.visitors import variable, assign
from core.backend.c.visitors.variable import resolve_variable
from typing import Any

def _compile_condition(condition: Any, block: Function | None = None) -> str:
    from core.backend.c.visitors.expression import format_expression
    return format_expression(condition, block)

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
        elif isinstance(item, MethodCall):
            from core.backend.c.visitors import method_call
            method_call.visit(item, is_statement=True, block=block)
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
        elif isinstance(item, WhileStatement):
            from core.backend.c.visitors import while_statement
            while_statement.visit(item, block)
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

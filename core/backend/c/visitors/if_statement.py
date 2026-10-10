from core.processor.objects import IfStatement, ForStatement, Call, Assign, Variable, Function, MethodCall
from core.backend.c.deffunc import deffunc
from core.backend.c.visitors import variable, assign
from core.backend.c.visitors.variable import resolve_variable
from typing import Any

def _compile_condition(condition: Any, block: Function | None = None) -> str:
    if isinstance(condition, (list, tuple)):
        if len(condition) == 2 and str(condition[0]) == 'not':
            target_obj = condition[1]
            if isinstance(target_obj, Call):
                call_res = deffunc(target_obj.name, target_obj.args, getattr(target_obj, 'kwargs', {}), is_statement=False, block=block)
                return f'!({call_res.compiled})'
            elif isinstance(target_obj, MethodCall):
                from core.backend.c.visitors import method_call
                call_res = method_call.visit(target_obj, is_statement=False, block=block)
                return f'!({call_res})'
            var_target = str(target_obj.value if hasattr(target_obj, 'value') else target_obj)
            resolved = resolve_variable(var_target, block)
            if resolved:
                resolved.uses += 1
                return f'!{resolved.name}'
            return f'!{var_target}'
        parts = []
        for p in condition:
            if isinstance(p, Call):
                call_res = deffunc(p.name, p.args, getattr(p, 'kwargs', {}), is_statement=False, block=block)
                parts.append(call_res.compiled)
            elif isinstance(p, MethodCall):
                from core.backend.c.visitors import method_call
                call_res = method_call.visit(p, is_statement=False, block=block)
                parts.append(call_res)
            elif str(p) == 'not':
                parts.append('!')
            elif str(p) in ('Null', 'None', 'null', 'NULL'):
                parts.append('NULL')
            else:
                val = str(p.value if hasattr(p, 'value') else p)
                resolved = resolve_variable(val, block)
                if resolved:
                    resolved.uses += 1
                    parts.append(resolved.name)
                else:
                    parts.append(val)
        raw_cond = ' '.join(parts).replace(' . ', '.')
        from core.backend.c.visitors.expression import format_expression
        return format_expression(raw_cond, block)
    if isinstance(condition, Call):
        call_res = deffunc(condition.name, condition.args, getattr(condition, 'kwargs', {}), is_statement=False, block=block)
        return call_res.compiled
    if isinstance(condition, MethodCall):
        from core.backend.c.visitors import method_call
        return method_call.visit(condition, is_statement=False, block=block)
    cond_str = str(condition.value if hasattr(condition, 'value') else condition)
    if cond_str in ('Null', 'None', 'null', 'NULL'):
        return 'NULL'
    resolved = resolve_variable(cond_str, block)
    if resolved:
        resolved.uses += 1
        return resolved.name
    from core.backend.c.visitors.expression import format_expression
    return format_expression(cond_str, block)

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

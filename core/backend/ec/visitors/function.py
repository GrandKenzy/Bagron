"""Emisor de C para declaraciones y definiciones de funciones (Backend EC).

Traduce objetos Function a funciones estándar en C (firma, parámetros, retorno y cuerpo).
"""

from typing import Any

from gram import ast
from core.backend.ec.visitors.assign import visit_assign
from core.backend.ec.visitors.variable import convert_type, resolve_value, visit_var
from core.processor.objects.assign import Assign
from core.processor.objects.call import Call
from core.processor.objects.function import Function
from core.processor.objects.if_statement import IfStatement
from core.processor.objects.method_call import MethodCall
from core.processor.objects.variable import Variable
from core.processor.objects.while_statement import WhileStatement


def _emit_statement(stmt: Any, storage: Any, expected_return: str, indent: int = 1) -> list[str]:
    ind = "    " * indent
    lines: list[str] = []

    if isinstance(stmt, Variable):
        decl, _ = visit_var(stmt, storage=storage)
        lines.append(f"{ind}{decl}")

    elif isinstance(stmt, Assign):
        code = visit_assign(stmt, storage=storage)
        lines.append(f"{ind}{code}")

    elif isinstance(stmt, Call):
        call_str = resolve_value(stmt, storage=storage)
        lines.append(f"{ind}{call_str};")

    elif isinstance(stmt, MethodCall):
        mc_str = resolve_value(stmt, storage=storage)
        lines.append(f"{ind}{mc_str};")

    elif isinstance(stmt, ast.ASTKeyword):
        if stmt.token.value == 'pass':
            pass

    elif isinstance(stmt, ast.ASTRef):
        if stmt.name == 'RETURN':
            has_val = len(stmt.nodes) > 1 and stmt.nodes[1] is not None
            if has_val:
                val_str = resolve_value(stmt.nodes[1], expected_type=expected_return, storage=storage)
                lines.append(f"{ind}return {val_str};")
            else:
                lines.append(f"{ind}return;")

        elif stmt.name == 'CALL':
            call_str = resolve_value(stmt, storage=storage)
            lines.append(f"{ind}{call_str};")

        elif stmt.name == 'SKIPER':
            token_val = stmt.nodes[0].token.value if stmt.nodes else 'continue'
            c_kw = 'continue' if token_val in ('next', 'continue') else 'break'
            lines.append(f"{ind}{c_kw};")

        elif stmt.name == 'MEMBER_CHAIN':
            chain_str = resolve_value(stmt, storage=storage)
            lines.append(f"{ind}{chain_str};")

    elif isinstance(stmt, IfStatement):
        cond_str = resolve_value(stmt.condition, storage=storage)
        lines.append(f"{ind}if ({cond_str}) {{")
        for sub_stmt in stmt.body:
            lines.extend(_emit_statement(sub_stmt, storage, expected_return, indent + 1))
        for elif_clause in stmt.elifs:
            elif_cond = resolve_value(elif_clause.condition, storage=storage)
            lines.append(f"{ind}}} else if ({elif_cond}) {{")
            for sub_stmt in elif_clause.body:
                lines.extend(_emit_statement(sub_stmt, storage, expected_return, indent + 1))
        if stmt.else_body:
            lines.append(f"{ind}}} else {{")
            for sub_stmt in stmt.else_body:
                lines.extend(_emit_statement(sub_stmt, storage, expected_return, indent + 1))
        lines.append(f"{ind}}}")

    elif isinstance(stmt, WhileStatement):
        cond_str = resolve_value(stmt.condition, storage=storage)
        lines.append(f"{ind}while ({cond_str}) {{")
        for sub_stmt in stmt.body:
            lines.extend(_emit_statement(sub_stmt, storage, expected_return, indent + 1))
        lines.append(f"{ind}}}")

    return lines


def visit_function(func: Function, storage: Any = None) -> tuple[str, str | None]:
    """Genera la definición y cabecera en C para una función."""
    name = func.c_name
    privacy = func.privacy
    is_inline = func.is_inline
    is_main = name == 'main'

    effective_storage = func.scope or storage

    # 1. Tipo de retorno
    ret_raw = func.return_type
    if effective_storage is not None and ret_raw != 'void':
        base_t = ret_raw.rstrip('*')
        st = effective_storage.find_struct(base_t)
        if st is not None:
            ret_raw = ret_raw.replace(base_t, st.c_name)
        else:
            en = effective_storage.find_enum(base_t)
            if en is not None:
                ret_raw = ret_raw.replace(base_t, en.c_name)
    c_ret_type = convert_type(ret_raw)

    # 2. Parámetros
    param_strs: list[str] = []
    for p in func.parameters:
        if p.is_variadic:
            param_strs.append('...')
        else:
            p_raw = p.type
            if effective_storage is not None:
                base_t = p_raw.rstrip('*')
                st = effective_storage.find_struct(base_t)
                if st is not None:
                    p_raw = p_raw.replace(base_t, st.c_name)
                else:
                    en = effective_storage.find_enum(base_t)
                    if en is not None:
                        p_raw = p_raw.replace(base_t, en.c_name)
            p_type = convert_type(p_raw)
            param_strs.append(f"{p_type} {p.name}")
    params_c = ', '.join(param_strs) if param_strs else 'void'

    # 3. Modificadores
    static_prefix = ('static ' if privacy == 'private' else '') if not is_main else ''
    inline_prefix = ('inline ' if is_inline else '') if not is_main else ''

    sig = f"{static_prefix}{inline_prefix}{c_ret_type} {name}({params_c})"

    # 4. Cuerpo de la función
    body_lines: list[str] = []
    if isinstance(func.body, list):
        for stmt in func.body:
            body_lines.extend(_emit_statement(stmt, effective_storage, func.return_type, indent=1))

    if not body_lines:
        if func.return_type != 'void' and is_main:
            body_lines.append("    return 0;")
        else:
            body_lines.append("    /* empty */")

    body_code = "\n".join(body_lines)
    decl = f"{sig} {{\n{body_code}\n}}"

    # 5. Cabecera (.h)
    header: str | None = None
    if privacy == 'public' and not is_main:
        header = f"{c_ret_type} {name}({params_c});"

    return (decl, header)


__all__ = ['visit_function']

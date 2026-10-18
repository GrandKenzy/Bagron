"""Emisor de C para declaraciones y asignaciones de variables (Backend EC).

Este módulo traduce objetos Variable del procesador semántico a código C estándar,
generando tanto la definición de la variable en el archivo de código (.c) como su
declaración 'extern' opcional para el encabezado (.h) cuando la visibilidad es pública.
"""

from typing import Any

from gram import ast
from gram.core.combinators.expressions import ASTBinaryOp, ASTUnaryOp
from gram.core.lexer.tokens import TokenType

from core.processor.objects.call import Call
from core.processor.objects.expression import (
    BinaryExpr,
    IndexAccess,
    LiteralExpr,
    UnaryExpr,
    VariableExpr,
)
from core.processor.objects.function import Function
from core.processor.objects.member_access import MemberAccess
from core.processor.objects.method_call import MethodCall
from core.processor.objects.variable import Variable
from core.processor.visitors.utils import extract_chain_items, get_node_value

# ==============================================================================
# CONVERSIÓN DE TIPOS DE EASY-C A C
# ==============================================================================
TYPE_MAP: dict[str, str] = {
    'int': 'int',
    'int8': 'int8_t',
    'int16': 'int16_t',
    'int32': 'int32_t',
    'int64': 'int64_t',
    'uint': 'uint32_t',
    'uint8': 'uint8_t',
    'byte': 'uint8_t',
    'uint16': 'uint16_t',
    'uint32': 'uint32_t',
    'uint64': 'uint64_t',
    'middle': '_Float16',
    'float': 'float',
    'double': 'double',
    'bool': 'bool',
    'char': 'char',
    'chain': 'char*',
    'ptr': 'void*',
    'cptr': 'void* const',
    'void': 'void',
    'wsize': 'size_t',
}



def convert_type(t: str) -> str:
    """Convierte una cadena de tipo de Easy-C a su tipo equivalente en C estándar."""
    t = t.strip()
    

    # Si es arreglo 'array[T, N]' o 'array[T]', extraer el tipo del elemento
    if t.startswith('array[') and t.endswith(']'):
        inner = t[6:-1].strip()
        parts = [p.strip() for p in inner.split(',')]
        return convert_type(parts[0])

    if t in TYPE_MAP:
        return TYPE_MAP[t]

    if t.endswith('*'):
        base = t[:-1].rstrip()
        return f"{convert_type(base)}*"

    return t


# ==============================================================================
# RESOLUCIÓN DE EXPRESIONES Y VALORES A C
# ==============================================================================
def resolve_value(node: Any, expected_type: str | None = None, storage: Any = None) -> str:
    """Traduce un valor (nodo AST, expresión IR o literal primitivo) a una expresión en C."""
    if node is None:
        return ''

    # 1. Literales primitivos de Python
    if isinstance(node, bool):
        return 'true' if node else 'false'

    if isinstance(node, (int, float)):
        return str(node)

    if isinstance(node, str):
        # Si ya está entrecomillado, respetarlo
        if (node.startswith('"') and node.endswith('"')) or (node.startswith("'") and node.endswith("'")):
            if expected_type == 'char':
                clean_char = node.strip("\"'")
                return f"'{clean_char}'"
            return node
        if expected_type in ('chain', 'char*'):
            return f'"{node}"'

        if expected_type == 'char':
            return f"'{node}'"
        if node == 'Null':
            return 'NULL'

        # Resolución de identificador si existe en storage
        if storage is not None:
            resolved = storage.resolve(node)
            if resolved is not None and isinstance(resolved, Variable):
                return resolved.c_name

        return node

    # 2. Nodos Literales de Gram
    if isinstance(node, ast.LiteralNumber):
        return str(node.token.value)

    if isinstance(node, ast.LiteralString):
        val = node.token.value.strip("\"'")
        if expected_type == 'char':
            return f"'{val}'"
        return f'"{val}"'

    # 3. Nodos de Token de Gram
    if isinstance(node, ast.ASTTokenNode):
        tok_val = str(node.token.value) if node.token.value is not None else ''
        tok_type_str = str(node.token.token)
        if tok_val == 'Null' or 'NULL' in tok_type_str:
            return 'NULL'
        if tok_val.lower() == 'true':
            return 'true'
        if tok_val.lower() == 'false':
            return 'false'
        if 'STRING' in tok_type_str or (tok_val.startswith(('"', "'")) and tok_val.endswith(('"', "'"))):
            clean_str = tok_val.strip("\"'")
            if expected_type == 'char':
                return f"'{clean_str}'"
            return f'"{clean_str}"'

        # Si es un IDENT y existe en storage, usar su c_name
        if storage is not None:
            resolved = storage.resolve(tok_val)
            if resolved is not None:
                if isinstance(resolved, Variable):
                    return resolved.c_name
                if isinstance(resolved, Function):
                    return resolved.c_name

        return tok_val


    # 4. Operaciones Binarias y Unarias de Gram
    if isinstance(node, ASTBinaryOp):
        c_op = node.operator.value if isinstance(node.operator, TokenType) else str(node.operator)
        op_map = {'and': '&&', 'or': '||'}
        c_op = op_map.get(c_op, c_op)
        left_str = resolve_value(node.left, expected_type, storage=storage)
        right_str = resolve_value(node.right, expected_type, storage=storage)
        return f"({left_str} {c_op} {right_str})"

    if isinstance(node, ASTUnaryOp):
        c_op = node.operator.value if isinstance(node.operator, TokenType) else str(node.operator)
        op_map = {'not': '!'}
        c_op = op_map.get(c_op, c_op)
        operand_str = resolve_value(node.operand, expected_type, storage=storage)
        return f"({c_op}{operand_str})"

    # 5. Nodos Array de Gram
    if isinstance(node, ast.ArrayNode):
        items_str = ', '.join(resolve_value(item, expected_type, storage=storage) for item in node.items)
        return f"{{{items_str}}}"

    # 6. Referencias AST (ASTRef)
    if isinstance(node, ast.ASTRef):
        if node.name in ('VALUE', 'DUALEXPR'):
            if len(node.nodes) == 1:
                return resolve_value(node.nodes[0], expected_type, storage=storage)
            return ' '.join(resolve_value(child, expected_type, storage=storage) for child in node.nodes)

        if node.name == 'ARRAY':
            items = [resolve_value(child, expected_type, storage=storage) for child in node.nodes]
            return f"{{{', '.join(items)}}}"

        if node.name == 'CALL':
            callee_name = get_node_value(node.nodes[0])
            from core.backend.ec.visitors.intrinsics import is_intrinsic, visit_intrinsic

            raw_args: list[Any] = []
            if len(node.nodes) > 1:
                args_node = node.nodes[1]
                if isinstance(args_node, ast.ASTRef) and args_node.nodes:
                    first = args_node.nodes[0]
                    raw_args = first.items if isinstance(first, ast.ArrayNode) else args_node.nodes

            if is_intrinsic(callee_name):
                return visit_intrinsic(callee_name, raw_args, kwargs=None, storage=storage)

            if storage is not None:
                st = storage.find_struct(callee_name) or storage.structs.get(callee_name)
                if st is not None:
                    args = [resolve_value(a, storage=storage) for a in raw_args]
                    body_args = ', '.join(args)
                    return f"({st.c_name}){{{body_args}}}" if body_args else f"({st.c_name}){{0}}"
                fn = storage.find_function(callee_name)
                if fn is not None:
                    callee_name = fn.c_name
            args = [resolve_value(a, storage=storage) for a in raw_args]
            return f"{callee_name}({', '.join(args)})"

        if node.name == 'MEMBER_CHAIN':
            items = extract_chain_items(node)
            item_strs = [get_node_value(it) for it in items]

            if storage is not None and len(item_strs) == 2:
                # Caso acceso a enum: Enum.MIEMBRO -> _ec_{prefix}_Enum_MIEMBRO
                enum_obj = storage.find_enum(item_strs[0]) or storage.enums.get(item_strs[0])
                if enum_obj is not None and item_strs[1] in enum_obj.members:
                    return f"{enum_obj.c_name}_{item_strs[1]}"

                # Caso acceso a módulo importado: modulo.variable o modulo.funcion
                mod_name, sym_name = item_strs[0], item_strs[1]
                if mod_name in storage.modules:
                    mod_storage = storage.modules[mod_name]
                    if sym_name in mod_storage.variables:
                        return mod_storage.variables[sym_name].c_name
                    if sym_name in mod_storage.functions:
                        return mod_storage.functions[sym_name].c_name

            parts = [resolve_value(it, storage=storage) for it in items]
            return '.'.join(parts)

        if node.name == 'INDEX_ACCESS':
            target = resolve_value(node.nodes[0], storage=storage)
            index = resolve_value(node.nodes[1], storage=storage)
            return f"{target}[{index}]"

    # 7. Objetos de Expresión del IR de Easy-C
    if isinstance(node, Call):
        from core.backend.ec.visitors.intrinsics import is_intrinsic, visit_intrinsic
        if is_intrinsic(node.name):
            return visit_intrinsic(node.name, node.args, kwargs=node.kwargs, storage=storage)

        callee_name = node.name
        if storage is not None:
            st = storage.find_struct(callee_name) or storage.structs.get(callee_name)
            if st is not None:
                body_args = ', '.join(resolve_value(a, storage=storage) for a in node.args)
                return f"({st.c_name}){{{body_args}}}" if body_args else f"({st.c_name}){{0}}"
            fn = storage.find_function(callee_name)
            if fn is not None:
                callee_name = fn.c_name
        args_str = ', '.join(resolve_value(a, storage=storage) for a in node.args)
        return f"{callee_name}({args_str})"

    if isinstance(node, MethodCall):
        target_str = resolve_value(node.target, storage=storage)
        args_str = ', '.join(resolve_value(a, storage=storage) for a in node.args)
        if target_str:
            return f"{target_str}.{node.method}({args_str})"
        return f"{node.method}({args_str})"

    if isinstance(node, MemberAccess):
        if storage is not None:
            target_name = node.target if isinstance(node.target, str) else None
            if target_name:
                # Caso acceso a enum: Enum.MIEMBRO -> _ec_{prefix}_Enum_MIEMBRO
                enum_obj = storage.find_enum(target_name) or storage.enums.get(target_name)
                if enum_obj is not None and node.member in enum_obj.members:
                    return f"{enum_obj.c_name}_{node.member}"

                # Comprobar si target es un módulo
                if target_name in storage.modules:
                    mod_storage = storage.modules[target_name]
                    if node.member in mod_storage.variables:
                        return mod_storage.variables[node.member].c_name
                    if node.member in mod_storage.functions:
                        return mod_storage.functions[node.member].c_name

        target_str = resolve_value(node.target, storage=storage)
        return f"{target_str}.{node.member}"

    if isinstance(node, IndexAccess):
        target_str = resolve_value(node.target, storage=storage)
        index_str = resolve_value(node.index, storage=storage)
        return f"{target_str}[{index_str}]"

    if isinstance(node, BinaryExpr):
        left_str = resolve_value(node.left, storage=storage)
        right_str = resolve_value(node.right, storage=storage)
        op_map = {'and': '&&', 'or': '||'}
        c_op = op_map.get(node.operator, node.operator)
        return f"({left_str} {c_op} {right_str})"

    if isinstance(node, UnaryExpr):
        operand_str = resolve_value(node.operand, storage=storage)
        op_map = {'not': '!'}
        c_op = op_map.get(node.operator, node.operator)
        return f"({c_op}{operand_str})"

    if isinstance(node, LiteralExpr):
        return str(node.value)

    if isinstance(node, VariableExpr):
        if storage is not None:
            resolved = storage.resolve(node.name)
            if resolved is not None and isinstance(resolved, Variable):
                return resolved.c_name
        return node.name

    return str(node)


# ==============================================================================
# VISITOR PRINCIPAL DE VARIABLES
# ==============================================================================
def visit_var(v: Variable, storage: Any = None) -> tuple[str, str | None]:
    """Genera la declaración/definición en C y la cabecera externa correspondiente.

    Retorna:
        tuple[str, str | None]:
            - decl: Código C de definición para el archivo fuente (terminado en ';').
            - header: Código C de declaración 'extern' para el archivo de cabecera (.h)
                      si la privacidad es pública, o None si es privada.
    """
    name: str = v.c_name
    privacy: str = v.privacy
    is_const: bool = v.is_constant
    is_cptr = v.is_cptr
    is_ptr = v.is_ptr
    raw_type: str = v.type
    fixed_size: int | None = v.fixed_size

    # Si el tipo base es un struct o enum en storage, usar su c_name mangled
    def _resolve_mangled_type(t_name: str) -> str:
        if storage is None:
            return t_name
        base = t_name.rstrip('*')
        st = storage.find_struct(base)
        if st is not None:
            return t_name.replace(base, st.c_name)
        en = storage.find_enum(base)
        if en is not None:
            return t_name.replace(base, en.c_name)
        return t_name

    effective_raw_type = _resolve_mangled_type(raw_type)
    c_type = convert_type(effective_raw_type)

    # Resolución del valor de inicialización
    val_str = resolve_value(v.value, expected_type=raw_type, storage=storage) if v.value is not None else ''

    # Prefijo static para variables privadas a nivel de archivo/monolito
    static_prefix = 'static ' if privacy == 'private' else ''

    # 1. Caso especial: Arreglos encapsulados en Array o de tamaño fijo
    if v.array is not None or fixed_size is not None:
        elem_raw_type = v.array.element_type if v.array is not None else raw_type
        elem_c_type = convert_type(_resolve_mangled_type(elem_raw_type))
        if v.array is not None and v.array.is_cptr:
            elem_c_type = f"{elem_c_type}* const"
        elif v.array is not None and v.array.is_ptr:
            elem_c_type = f"{elem_c_type}*"
        size_val = v.array.size if v.array is not None else fixed_size
        size_part = f"[{size_val}]" if size_val is not None else "[]"
        init_part = f" = {val_str}" if val_str else ""
        const_prefix = 'const ' if is_const else ''
        decl = f"{static_prefix}{const_prefix}{elem_c_type} {name}{size_part}{init_part};"

        header: str | None = None
        if privacy == 'public':
            header = f"extern {const_prefix}{elem_c_type} {name}{size_part};"

        return (decl, header)

    # 2. Caso especial: Puntero constante a datos mutables (cptr)
    if is_cptr:
        # En C: T* const p = valor; (el puntero es const, los datos son mutables)
        base_ptr_type = f"{c_type}* const"
        init_part = f" = {val_str}" if val_str else ""
        decl = f"{static_prefix}{base_ptr_type} {name}{init_part};"

        header = None
        if privacy == 'public':
            header = f"extern {base_ptr_type} {name};"
        return (decl, header)

    # 3. Caso especial: Puntero no-constante (ptr)
    if is_ptr:
        base_ptr_type = f"{c_type}*"
        const_prefix = 'const ' if is_const else ''
        init_part = f" = {val_str}" if val_str else ""
        decl = f"{static_prefix}{const_prefix}{base_ptr_type} {name}{init_part};"

        header = None
        if privacy == 'public':
            header = f"extern {const_prefix}{base_ptr_type} {name};"

        return (decl, header)

    # 4. Caso general: Variables escalares, punteros y estructuras
    const_prefix = 'const ' if is_const else ''
    init_part = f" = {val_str}" if val_str else ""
    decl = f"{static_prefix}{const_prefix}{c_type} {name}{init_part};"

    header = None
    if privacy == 'public':
        header = f"extern {const_prefix}{c_type} {name};"



    return (decl, header)


__all__ = [
    'convert_type',
    'resolve_value',
    'visit_var',
]
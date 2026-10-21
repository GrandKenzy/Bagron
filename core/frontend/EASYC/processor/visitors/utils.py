"""Utilidades compartidas para los visitors del procesador semántico."""
from typing import Any
from gram import ast
from core.processor.objects.function import Function, LocalStorage
from core.processor.objects.variable import Variable


def get_node_value(node: Any) -> str:
    """Extrae el valor textual de un nodo AST (Token o ASTTokenNode) o su representación en cadena."""
    if isinstance(node, ast.ASTTokenNode):
        return node.token.value
    return str(node)


def extract_chain_items(node: ast.ASTRef) -> list[Any]:
    """Extrae los elementos de un nodo MEMBER_CHAIN si contiene un ArrayNode."""
    if node.nodes and isinstance(node.nodes[0], ast.ArrayNode):
        return list(node.nodes[0].items)
    return []


def get_enclosing_function(storage: Any) -> Function | None:
    """Retorna la función contenedora si el almacenamiento actual es un LocalStorage."""
    if isinstance(storage, LocalStorage):
        return storage.function
    return None


def is_constant_variable(var_obj: Any) -> bool:
    """Comprueba si un objeto resuelto es una variable constante."""
    return isinstance(var_obj, Variable) and var_obj.is_constant


def extract_constant_int(node: Any) -> int | None:
    """Extrae el valor numérico entero constante de un nodo AST si es resoluble estáticamente."""
    if node is None:
        return None

    from gram.core.combinators.expressions import ASTUnaryOp
    from gram.core.lexer.tokens import TokenType

    if isinstance(node, ASTUnaryOp):
        op_str = node.operator.value if isinstance(node.operator, TokenType) else str(node.operator)
        val = extract_constant_int(node.operand)
        if val is not None:
            if op_str == '-':
                return -val
            elif op_str == '+':
                return val
        return None

    if isinstance(node, ast.LiteralNumber):
        try:
            return int(node.token.value)
        except (ValueError, TypeError):
            return None

    if isinstance(node, ast.ASTTokenNode):
        try:
            return int(node.token.value)
        except (ValueError, TypeError):
            return None

    if isinstance(node, ast.ASTRef):
        if len(node.nodes) == 1:
            return extract_constant_int(node.nodes[0])
        elif len(node.nodes) == 2 and isinstance(node.nodes[0], ast.ASTTokenNode) and node.nodes[0].token.value == '-':
            sub_val = extract_constant_int(node.nodes[1])
            if sub_val is not None:
                return -sub_val

    return None


def parse_array_type(array_type_str: str) -> tuple[str, int | None]:
    """Parsea una representación 'array[T, N]' o 'array[T]' en (tipo_elemento, tamaño_o_None)."""
    if not (array_type_str.startswith('array[') and array_type_str.endswith(']')):
        return array_type_str, None
    inner = array_type_str[6:-1].strip()
    depth = 0
    comma_idx = -1
    for i, ch in enumerate(inner):
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
        elif ch == ',' and depth == 0:
            comma_idx = i
            break
    if comma_idx != -1:
        elem_t = inner[:comma_idx].strip()
        size_str = inner[comma_idx + 1:].strip()
        try:
            return elem_t, int(size_str)
        except ValueError:
            return elem_t, None
    return inner, None


__all__ = [
    'get_node_value',
    'extract_chain_items',
    'get_enclosing_function',
    'is_constant_variable',
    'extract_constant_int',
    'parse_array_type',
]


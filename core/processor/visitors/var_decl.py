"""Visitante y procesador semántico de declaraciones de variables (Easy-C).

Maneja la inferencia de tipos, validación semántica de compatibilidad y registro
en el almacenamiento (Storage / LocalStorage) para variables escalares, punteros,
arreglos de tamaño fijo y asignaciones múltiples.
"""

from typing import Any

from gram import ast
from gram.core.combinators.expressions import ASTBinaryOp
from gram.core.lexer.tokens import TokenType

from core.processor.objects.array import Array
from core.processor.objects.function import FunctionParam, LocalStorage
from core.processor.objects.variable import Variable
from core.processor.storage import Storage

from core.processor.visitors.utils import (
    extract_chain_items,
    extract_constant_int,
    get_node_value,
)

# Categorías de tipos para validación semántica
INTEGER_TYPES = {
    'int', 'int8', 'int16', 'int32', 'int64',
    'uint', 'uint8', 'uint16', 'uint32', 'uint64',
    'byte',
    'wsize',
}
FLOAT_TYPES = {'middle', 'float', 'double'}
BOOL_TYPES = {'bool'}
STRING_TYPES = {'chain'}
CHAR_TYPES = {'char'}

COMPARISON_LOGICAL_OPS = {'==', '!=', '<', '>', '<=', '>=', 'and', 'or', 'not'}
NULL_LITERALS = {'Null'}
BOOLEAN_LITERALS = {'true', 'false'}
RESERVED_IDENTIFIERS = {'self', 'cls'}


# ==============================================================================
# EXTRACCIÓN DE TIPOS DESDE EL AST
# ==============================================================================

def extract_type(segment_type: ast.ASTRef) -> str:
    """Extrae el tipo representativo de un nodo SEGMENT_TYPE."""
    type_node = segment_type.nodes[0]
    if isinstance(type_node, ast.ASTRef):
        if type_node.name == 'POINTER_TYPE':
            pointer_token = type_node.nodes[0]
            if isinstance(pointer_token, ast.ASTTokenNode):
                return pointer_token.token.value
            return str(pointer_token)

        if type_node.name == 'ARRAY':
            element_node = type_node.nodes[2]
            if isinstance(element_node, ast.ASTRef):
                element_type = extract_type(element_node)
            elif isinstance(element_node, ast.ASTTokenNode):
                element_type = element_node.token.value
            else:
                element_type = str(element_node)
            return f"array[{element_type}]"

    if isinstance(type_node, ast.ASTTokenNode):
        return type_node.token.value
    return str(type_node)


def extract_pointer_base_type(segment_type: ast.ASTRef) -> str | None:
    """Extrae el tipo base al que apunta el puntero (ej: 'int' en 'cptr int' -> 'int').

    Si el puntero se declaró sin tipo base (ej: 'cptr p' o 'ptr p'), retorna None
    indicando que es un puntero genérico (void* / void* const).
    """
    if not segment_type or not segment_type.nodes:

        return None

    type_node = segment_type.nodes[0]
    if isinstance(type_node, ast.ASTRef) and type_node.name == 'POINTER_TYPE':
        if len(type_node.nodes) > 1:
            base_node = type_node.nodes[1]
            if isinstance(base_node, ast.ASTRef):
                if base_node.name == 'ARRAY':
                    element_node = base_node.nodes[2]
                    if isinstance(element_node, ast.ASTRef):
                        element_type = extract_type(element_node)
                    elif isinstance(element_node, ast.ASTTokenNode):
                        element_type = element_node.token.value
                    else:
                        element_type = str(element_node)
                    return f"array[{element_type}]"
                return extract_type(base_node)

            if isinstance(base_node, ast.ASTTokenNode):
                return base_node.token.value
            return str(base_node)
    return None


def extract_array_size(segment_type: ast.ASTRef) -> int | None:
    """Extrae el tamaño fijo de un nodo ARRAY dentro de SEGMENT_TYPE si está definido."""
    if not segment_type or not segment_type.nodes:
        return None

    type_node = segment_type.nodes[0]
    if isinstance(type_node, ast.ASTRef) and type_node.name == 'ARRAY':
        if len(type_node.nodes) > 4 and type_node.nodes[4] is not None:
            return extract_constant_int(type_node.nodes[4])
    return None


def extract_array_info(segment_type: ast.ASTRef) -> Array | None:
    """Extrae un objeto Array a partir de un nodo SEGMENT_TYPE si define un arreglo."""
    if not segment_type or not segment_type.nodes:
        return None

    type_node = segment_type.nodes[0]
    if isinstance(type_node, ast.ASTRef) and type_node.name == 'ARRAY':
        element_node = type_node.nodes[2]
        if isinstance(element_node, ast.ASTRef):
            element_type = extract_type(element_node)
            pointer_base = extract_pointer_base_type(element_node)
        elif isinstance(element_node, ast.ASTTokenNode):
            element_type = element_node.token.value
            pointer_base = None
        else:
            element_type = str(element_node)
            pointer_base = None

        size = None
        if len(type_node.nodes) > 4 and type_node.nodes[4] is not None:
            size = extract_constant_int(type_node.nodes[4])

        return Array(
            element_type=element_type,
            size=size,
            is_cptr=(element_type == 'cptr'),
            is_ptr=(element_type == 'ptr'),
            pointer_base_type=pointer_base,
        )
    return None



# ==============================================================================
# INFERENCIA DE TIPOS
# ==============================================================================

def _infer_binary_op(storage: Any, node: ASTBinaryOp) -> str | None:
    left_type = _infer_node(storage, node.left)
    right_type = _infer_node(storage, node.right)

    operator_str = node.operator.value if isinstance(node.operator, TokenType) else str(node.operator)
    if operator_str in COMPARISON_LOGICAL_OPS:
        return 'bool'

    if left_type == 'float' or right_type == 'float':
        return 'float'
    if left_type == 'int' and right_type == 'int':
        return 'int'
    return left_type or right_type



def _infer_ast_ref(storage: Any, node: ast.ASTRef) -> str | None:
    if node.name in ('VALUE', 'DUALEXPR'):
        if len(node.nodes) == 1:
            return _infer_node(storage, node.nodes[0])

        token_values = [n.token.value for n in node.nodes if isinstance(n, ast.ASTTokenNode)]
        if any(op in COMPARISON_LOGICAL_OPS for op in token_values):
            return 'bool'

        has_float = any(
            ('.' in n.token.value)
            for n in node.nodes
            if isinstance(n, ast.LiteralNumber) or (isinstance(n, ast.ASTTokenNode) and 'NUMBER' in str(n.token.token))
        )
        if has_float:
            return 'float'

        has_number = any(
            isinstance(n, ast.LiteralNumber) or (isinstance(n, ast.ASTTokenNode) and 'NUMBER' in str(n.token.token))
            for n in node.nodes
        )
        if has_number:
            return 'int'
        return None

    if node.name == 'CALL':
        from core.processor.visitors.call import visit_call
        call_obj = visit_call(storage, node)
        return call_obj.returntype

    if node.name == 'MEMBER_CHAIN':
        from core.processor.objects.member_access import MemberAccess
        from core.processor.objects.method_call import MethodCall
        from core.processor.visitors.call import visit_member_chain
        result = visit_member_chain(storage, node)
        if isinstance(result, MethodCall) and result.returntype:
            return result.returntype
        if isinstance(result, MemberAccess) and result.inferred_type:
            return result.inferred_type
        return None

    if node.name == 'INDEX_ACCESS':
        from core.processor.visitors.call import visit_index_access
        index_obj = visit_index_access(storage, node)
        return index_obj.inferred_type

    return None


def _infer_token_node(storage: Any, node: ast.ASTTokenNode) -> str | None:
    token_kind = str(node.token.token)
    token_value = node.token.value

    if 'NUMBER' in token_kind:
        return 'float' if token_value and '.' in str(token_value) else 'int'

    if 'STRING' in token_kind or 'DOCSTRING' in token_kind:
        content = str(token_value).strip('"\'') if token_value else ''
        return 'char' if len(content) == 1 else 'chain'

    if 'NULL' in token_kind or token_value in NULL_LITERALS:
        return 'ptr'

    if 'BOOL' in token_kind or (isinstance(token_value, str) and token_value.lower() in BOOLEAN_LITERALS):
        return 'bool'

    if 'IDENT' in token_kind:
        identifier_name = str(token_value)
        resolved_symbol = storage.resolve(identifier_name)
        if isinstance(resolved_symbol, (Variable, FunctionParam)):
            return storage.resolve_type(resolved_symbol.type)
        raise RuntimeError(f"Variable '{identifier_name}' no está definida.")

    return None


def _infer_node(storage: Any, node: Any) -> str | None:
    if node is None:
        return None

    if isinstance(node, ASTBinaryOp):
        return _infer_binary_op(storage, node)

    if isinstance(node, ast.ASTRef):
        return _infer_ast_ref(storage, node)

    if isinstance(node, ast.LiteralNumber):
        return 'float' if isinstance(node.token.value, float) else 'int'

    if isinstance(node, ast.LiteralString):
        content = node.token.value.strip('"\'')
        return 'char' if len(content) == 1 else 'chain'

    if isinstance(node, ast.ASTTokenNode):
        return _infer_token_node(storage, node)

    return None


def infer_value_type(storage: Any, value_node: Any) -> str | None:
    """Infiere el tipo semántico de un nodo de expresión en el contexto de storage."""
    return _infer_node(storage, value_node)


# ==============================================================================
# VALIDACIÓN DE TIPOS
# ==============================================================================

def validate_type(var_name: str, var_type: str, inferred_type: str, storage: Any = None):
    """Valida la compatibilidad semántica entre el tipo declarado y el tipo inferido."""
    if storage is not None:
        var_type = storage.resolve_type(var_type)
        inferred_type = storage.resolve_type(inferred_type)

    if inferred_type == 'int':
        if (
            var_type not in INTEGER_TYPES
            and var_type not in FLOAT_TYPES
            and var_type not in ('ptr', 'cptr', 'any')
            and not var_type.endswith('*')
        ):
            raise TypeError(
                f"Incompatibilidad de tipos en '{var_name}': declarada como '{var_type}', pero se asignó un entero."
            )
    elif inferred_type == 'float':
        if var_type not in FLOAT_TYPES:
            raise TypeError(
                f"Incompatibilidad de tipos en '{var_name}': declarada como '{var_type}', pero se asignó un flotante."
            )
    elif inferred_type == 'bool':
        if var_type not in BOOL_TYPES:
            raise TypeError(
                f"Incompatibilidad de tipos en '{var_name}': declarada como '{var_type}', pero se asignó un booleano."
            )
    elif inferred_type == 'chain':
        if var_type not in STRING_TYPES:
            raise TypeError(
                f"Incompatibilidad de tipos en '{var_name}': declarada como '{var_type}', pero se asignó una cadena."
            )
    elif inferred_type == 'char':
        if var_type not in CHAR_TYPES and var_type not in STRING_TYPES:
            raise TypeError(
                f"Incompatibilidad de tipos en '{var_name}': declarada como '{var_type}', pero se asignó un caracter."
            )
    else:
        if (
            var_type != inferred_type
            and not (var_type in INTEGER_TYPES and inferred_type in INTEGER_TYPES)
            and not (var_type in ('ptr', 'cptr', 'any') or inferred_type in ('ptr', 'cptr', 'any'))
            and not (var_type.rstrip('*') == inferred_type.rstrip('*'))
        ):
            raise TypeError(
                f"Incompatibilidad de tipos en '{var_name}': declarada como '{var_type}', pero se asignó '{inferred_type}'."
            )


# ==============================================================================
# MANEJADORES DE CASOS DE DECLARACIÓN
# ==============================================================================

def _extract_ptr_modifier(node: ast.ASTRef) -> tuple[str | None, int]:
    """Retorna el modificador ('ptr', 'cptr' o None) y el índice inicial del target."""
    if node.nodes and isinstance(node.nodes[0], ast.ASTRef) and node.nodes[0].name == 'PTR_MODIFIER':
        ptr_tok = node.nodes[0].nodes[0]
        if isinstance(ptr_tok, ast.ASTTokenNode):
            return ptr_tok.token.value, 1
        return str(ptr_tok), 1
    return None, 0


def _assert_not_reserved_identifier(name: str) -> None:
    if name in RESERVED_IDENTIFIERS:
        raise RuntimeError(f"No se puede usar el identificador reservado '{name}' como nombre de variable.")


def _handle_multi_decl(storage: Storage, decl_node: ast.ASTRef, privacy: str) -> list[Variable]:
    """Maneja declaraciones múltiples (ej: a, b: int = x, y o ptr a, b: int = x, y)."""
    ptr_mod, start_idx = _extract_ptr_modifier(decl_node)
    targets_node = decl_node.nodes[start_idx]
    # colon is at decl_node.nodes[start_idx + 1]
    type_node = decl_node.nodes[start_idx + 2]
    # assign is at decl_node.nodes[start_idx + 3]
    values_node = decl_node.nodes[start_idx + 4]

    target_tokens = list(targets_node.items) if isinstance(targets_node, ast.ArrayNode) else [targets_node]
    value_nodes = list(values_node.items) if isinstance(values_node, ast.ArrayNode) else [values_node]

    if len(target_tokens) != len(value_nodes):
        raise RuntimeError(
            f"Desempaquetado inválido: se esperaban {len(target_tokens)} valores pero se recibieron {len(value_nodes)}."
        )

    base_type = extract_type(type_node)
    array_obj = extract_array_info(type_node)
    fixed_size = array_obj.size if array_obj else extract_array_size(type_node)

    if ptr_mod == 'cptr':
        declared_type = base_type
        pointer_base_type = base_type
        is_cptr = True
        is_ptr = False
        if array_obj:
            array_obj.is_cptr = True
            array_obj.is_ptr = False
            array_obj.element_type = base_type
    elif ptr_mod == 'ptr':
        declared_type = base_type
        pointer_base_type = base_type
        is_cptr = False
        is_ptr = True
        if array_obj:
            array_obj.is_cptr = False
            array_obj.is_ptr = True
            array_obj.element_type = base_type
    else:
        declared_type = base_type
        is_cptr = False
        is_ptr = False
        pointer_base_type = None

    created_variables: list[Variable] = []
    for target_token, val_node in zip(target_tokens, value_nodes):
        variable_name = get_node_value(target_token)
        _assert_not_reserved_identifier(variable_name)

        storage.collition_name(variable_name)
        inferred_type = infer_value_type(storage, val_node)
        if inferred_type is not None:
            validate_type(variable_name, pointer_base_type or declared_type, inferred_type, storage=storage)

        created_variables.append(
            storage.add_variable(
                name=variable_name,
                var_type=declared_type,
                value=val_node,
                privacy=privacy,
                fixed_size=fixed_size,
                pointer_base_type=pointer_base_type,
                is_cptr=is_cptr,
                is_ptr=is_ptr,
                array=array_obj,
            )
        )
    return created_variables


def _handle_member_chain_decl(
    storage: Storage,
    decl_node: ast.ASTRef,
    target_node: ast.ASTRef,
) -> Any:
    """Maneja declaraciones de atributos de miembros (ej: self.x: int = 10, ptr self.x = Null)."""
    items = extract_chain_items(target_node)
    base_name = get_node_value(items[0]) if items else ''
    field_name = get_node_value(items[1]) if len(items) > 1 else ''

    ptr_mod, start_idx = _extract_ptr_modifier(decl_node)

    if decl_node.name == 'VAR_FULL_DECL':
        type_node = decl_node.nodes[start_idx + 2]
        value_node = decl_node.nodes[start_idx + 4]
    elif decl_node.name == 'VAR_PARTIAL_DECL':
        type_node = decl_node.nodes[start_idx + 2]
        value_node = None
    elif decl_node.name == 'VAR_PTR_GENERIC_DECL':
        type_node = None
        value_node = decl_node.nodes[start_idx + 2]
    else:  # VAR_PTR_GENERIC_PARTIAL
        type_node = None
        value_node = None

    if base_name in RESERVED_IDENTIFIERS:
        current_func = storage.function if isinstance(storage, LocalStorage) else None
        from core.processor.objects.class_decl import ClassMethod
        if isinstance(current_func, ClassMethod) and current_func.kind == 'staticmethod':
            raise RuntimeError(f"No se puede usar '{base_name}' dentro del método estático '{current_func.name}'.")

    if type_node is not None:
        base_type = extract_type(type_node)
        declared_type = base_type
    else:
        declared_type = 'void' if ptr_mod else 'any'

    if value_node is not None:
        inferred_type = infer_value_type(storage, value_node)
        if inferred_type is not None:
            if ptr_mod:
                if declared_type != 'void':
                    validate_type(field_name, declared_type, inferred_type, storage=storage)
            else:
                validate_type(field_name, declared_type, inferred_type, storage=storage)

    from core.processor.objects.assign import Assign
    from core.processor.objects.member_access import MemberAccess

    member_access = MemberAccess(target=base_name, member=field_name, in_scope=storage, inferred_type=declared_type)
    return Assign(target=member_access, value=value_node, in_scope=storage)


def _handle_single_decl(
    storage: Storage,
    decl_node: ast.ASTRef,
    target_node: ast.ASTTokenNode,
    privacy: str,
) -> Variable:
    """Maneja declaraciones simples escalares, arreglos o punteros."""
    variable_name: str = target_node.token.value
    _assert_not_reserved_identifier(variable_name)

    ptr_mod, start_idx = _extract_ptr_modifier(decl_node)

    if decl_node.name == 'VAR_FULL_DECL':
        type_node = decl_node.nodes[start_idx + 2]
        value_node = decl_node.nodes[start_idx + 4]
    elif decl_node.name == 'VAR_PARTIAL_DECL':
        type_node = decl_node.nodes[start_idx + 2]
        value_node = None
    elif decl_node.name == 'VAR_PTR_GENERIC_DECL':
        type_node = None
        value_node = decl_node.nodes[start_idx + 2]
    else:  # VAR_PTR_GENERIC_PARTIAL
        type_node = None
        value_node = None

    storage.collition_name(variable_name)

    if ptr_mod == 'cptr':
        declared_type = extract_type(type_node) if type_node is not None else 'void'
        is_cptr = True
        is_ptr = False
        pointer_base_type = declared_type
        array_obj = extract_array_info(type_node) if type_node is not None else None
        fixed_size = array_obj.size if array_obj else (extract_array_size(type_node) if type_node is not None else None)
        if array_obj:
            array_obj.is_cptr = True
            array_obj.is_ptr = False
            array_obj.element_type = declared_type
    elif ptr_mod == 'ptr':
        declared_type = extract_type(type_node) if type_node is not None else 'void'
        is_cptr = False
        is_ptr = True
        pointer_base_type = declared_type
        array_obj = extract_array_info(type_node) if type_node is not None else None
        fixed_size = array_obj.size if array_obj else (extract_array_size(type_node) if type_node is not None else None)
        if array_obj:
            array_obj.is_cptr = False
            array_obj.is_ptr = True
            array_obj.element_type = declared_type
    else:
        declared_type = extract_type(type_node) if type_node is not None else 'any'
        is_cptr = False
        is_ptr = False
        pointer_base_type = None
        array_obj = extract_array_info(type_node) if type_node is not None else None
        fixed_size = array_obj.size if array_obj else (extract_array_size(type_node) if type_node is not None else None)

    if value_node is not None:
        inferred_type = infer_value_type(storage, value_node)
        if inferred_type is not None:
            if is_cptr or is_ptr:
                if declared_type != 'void':
                    validate_type(variable_name, declared_type, inferred_type, storage=storage)
            else:
                validate_type(variable_name, declared_type, inferred_type, storage=storage)

    return storage.add_variable(
        name=variable_name,
        var_type=declared_type,
        value=value_node,
        privacy=privacy,
        fixed_size=fixed_size,
        pointer_base_type=pointer_base_type,
        is_cptr=is_cptr,
        is_ptr=is_ptr,
        array=array_obj,
    )


# ==============================================================================
# DESPACHADOR PRINCIPAL
# ==============================================================================

def visit_var(storage: Storage, node: ast.ASTRef) -> Any:
    """Procesa un nodo VAR_DECL y despacha según el tipo de declaración."""
    decl_node: ast.ASTRef = node.nodes[-1]  # type: ignore
    privacy: str = node.nodes[0].token.value if len(node.nodes) == 2 else storage.privacy  # type: ignore

    if decl_node.name == 'VAR_MULTI_DECL':
        return _handle_multi_decl(storage, decl_node, privacy)

    ptr_mod, start_idx = _extract_ptr_modifier(decl_node)
    target_node = decl_node.nodes[start_idx]

    if isinstance(target_node, ast.ASTRef) and target_node.name == 'MEMBER_CHAIN':
        return _handle_member_chain_decl(storage, decl_node, target_node)

    return _handle_single_decl(storage, decl_node, target_node, privacy)  # type: ignore


__all__ = [
    'BOOL_TYPES',
    'CHAR_TYPES',
    'FLOAT_TYPES',
    'INTEGER_TYPES',
    'STRING_TYPES',
    '_extract_ptr_modifier',
    'extract_array_info',
    'extract_array_size',
    'extract_pointer_base_type',
    'extract_type',
    'infer_value_type',
    'validate_type',
    'visit_var',
]
from typing import Any

from gram import ast

from core.processor.objects.assign import Assign
from core.processor.objects.class_decl import ClassDecl
from core.processor.objects.function import FunctionParam
from core.processor.objects.member_access import MemberAccess
from core.processor.objects.variable import Variable
from core.processor.storage import Storage
from core.processor.visitors.utils import extract_chain_items, get_node_value
from core.processor.visitors.var_decl import (
    CHAR_TYPES,
    FLOAT_TYPES,
    INTEGER_TYPES,
    STRING_TYPES,
    infer_value_type,
    validate_type,
)

COMPOUND_OPS = {
    '+=', '-=', '*=', '/=', '%=',
    '&=', '|=', '^=', '<<=', '>>=',
}


def validate_compound_assignment(
    target_repr: str,
    target_type: str,
    op: str,
    value_type: str | None = None,
    storage: Any = None,
    is_pointer: bool = False,
) -> None:
    """Valida que el operador compuesto sea compatible con el tipo destino y el tipo de valor."""
    if op == '=':
        return

    if op not in COMPOUND_OPS:
        raise TypeError(f"Operador de asignación '{op}' no reconocido en '{target_repr}'.")

    if storage is not None:
        target_type = storage.resolve_type(target_type)
        if value_type is not None:
            value_type = storage.resolve_type(value_type)

    is_int_target = target_type in INTEGER_TYPES
    is_float_target = target_type in FLOAT_TYPES
    is_str_target = target_type in STRING_TYPES
    is_ptr_target = is_pointer or target_type in ('ptr', 'pointer', 'cptr') or target_type.endswith('*')
    is_flags_target = storage is not None and target_type in storage.flags

    if op == '+=':
        if not (is_int_target or is_float_target or is_str_target or is_ptr_target or target_type == 'any'):
            raise TypeError(f"El operador '+=' no está permitido para el tipo '{target_type}' en '{target_repr}'.")
        if value_type is not None and value_type != 'any':
            if is_int_target and value_type not in INTEGER_TYPES:
                raise TypeError(f"Incompatibilidad de tipos en operador '+=': '{target_type}' no puede sumar '{value_type}'.")
            elif is_float_target and (value_type not in FLOAT_TYPES and value_type not in INTEGER_TYPES):
                raise TypeError(f"Incompatibilidad de tipos en operador '+=': '{target_type}' no puede sumar '{value_type}'.")
            elif is_str_target and (value_type not in STRING_TYPES and value_type not in CHAR_TYPES):
                raise TypeError(f"Incompatibilidad de tipos en operador '+=': 'str' solo puede concatenar 'str' o 'char', no '{value_type}'.")
            elif is_ptr_target and value_type not in INTEGER_TYPES:
                raise TypeError(f"Incompatibilidad de tipos en operador '+=': aritmética de punteros requiere entero, no '{value_type}'.")

    elif op == '-=':
        if not (is_int_target or is_float_target or is_ptr_target or target_type == 'any'):
            raise TypeError(f"El operador '-=' no está permitido para el tipo '{target_type}' en '{target_repr}'.")
        if value_type is not None and value_type != 'any':
            if is_int_target and value_type not in INTEGER_TYPES:
                raise TypeError(f"Incompatibilidad de tipos en operador '-=': '{target_type}' no puede restar '{value_type}'.")
            elif is_float_target and (value_type not in FLOAT_TYPES and value_type not in INTEGER_TYPES):
                raise TypeError(f"Incompatibilidad de tipos en operador '-=': '{target_type}' no puede restar '{value_type}'.")
            elif is_ptr_target and value_type not in INTEGER_TYPES:
                raise TypeError(f"Incompatibilidad de tipos en operador '-=': aritmética de punteros requiere entero, no '{value_type}'.")

    elif op in ('*=', '/='):
        if not (is_int_target or is_float_target or target_type == 'any'):
            raise TypeError(f"El operador '{op}' no está permitido para el tipo '{target_type}' en '{target_repr}'.")
        if value_type is not None and value_type != 'any':
            if is_int_target and value_type not in INTEGER_TYPES:
                raise TypeError(f"Incompatibilidad de tipos en operador '{op}': '{target_type}' requiere entero, no '{value_type}'.")
            elif is_float_target and (value_type not in FLOAT_TYPES and value_type not in INTEGER_TYPES):
                raise TypeError(f"Incompatibilidad de tipos en operador '{op}': '{target_type}' requiere número, no '{value_type}'.")

    elif op == '%=':
        if not (is_int_target or target_type == 'any'):
            raise TypeError(f"El operador '%=' solo está permitido para tipos enteros, no para '{target_type}' en '{target_repr}'.")
        if value_type is not None and value_type != 'any':
            if value_type not in INTEGER_TYPES:
                raise TypeError(f"Incompatibilidad de tipos en operador '%=': se esperaba un entero, se obtuvo '{value_type}'.")

    elif op in ('&=', '|=', '^=', '<<=', '>>='):
        if not (is_int_target or is_flags_target or target_type == 'any'):
            raise TypeError(f"El operador bitwise '{op}' solo está permitido para enteros o flags, no para '{target_type}' en '{target_repr}'.")
        if value_type is not None and value_type != 'any':
            if not (value_type in INTEGER_TYPES or (storage is not None and value_type in storage.flags)):
                raise TypeError(f"Incompatibilidad de tipos en operador '{op}': se requiere entero o flags, no '{value_type}'.")


def visit_assign(storage: Storage, node: ast.ASTRef) -> Assign:
    target_node = node.nodes[0]
    if isinstance(target_node, ast.ASTRef) and target_node.name == 'ASSIGN_TARGET':
        target_node = target_node.nodes[0]

    op: str = get_node_value(node.nodes[1])
    value_node: ast.ASTRef = node.nodes[2]  # type: ignore
    inferred = infer_value_type(storage, value_node)

    # Caso 1: Asignación a índice (ej: arr[0] = 5, matrix[1][2] = 10, p.data[0] = 5)
    if isinstance(target_node, ast.ASTRef) and target_node.name == 'INDEX_ACCESS':
        from core.processor.visitors.call import visit_index_access
        idx_obj = visit_index_access(storage, target_node)

        root_node = target_node.nodes[0]
        if isinstance(root_node, ast.ASTTokenNode):
            root_name = root_node.token.value
            root_obj = storage.resolve(root_name)
            if isinstance(root_obj, Variable) and root_obj.is_constant and not root_obj.is_cptr:
                raise RuntimeError(f"No se puede modificar el elemento de la constante '{root_name}'.")

        target_type = idx_obj.inferred_type or 'any'
        target_repr = idx_obj.value
        if op == '=':
            if inferred is not None and target_type != 'any':
                validate_type(target_repr, target_type, inferred, storage=storage)
        else:
            validate_compound_assignment(target_repr, target_type, op, inferred, storage=storage)

        return Assign(target=idx_obj, value=value_node, op=op, in_scope=storage)


    # Caso 2: Asignación a miembro de struct o clase (soporta anidamiento arbitrario ASG-02)
    elif isinstance(target_node, ast.ASTRef) and target_node.name == 'MEMBER_CHAIN':
        items = extract_chain_items(target_node)
        if not items:
            raise RuntimeError("Cadena de miembros vacía.")
        base_name = get_node_value(items[0])
        target_repr = '.'.join(get_node_value(it) for it in items)

        # 1. Asignación sobre self
        if base_name == 'self':
            self_var = storage.resolve('self')
            if self_var is None:
                raise RuntimeError("Variable 'self' no ha sido declarada.")
            self_var.uses += 1
            raw_t = self_var.type.rstrip('*')
            is_in_new = raw_t.endswith('_Class')
            c_name = raw_t[:-6] if is_in_new else raw_t
            c_obj = storage.classes.get(c_name)
            if c_obj is None:
                raise RuntimeError(f"Clase '{c_name}' de 'self' no encontrada.")

            first_name = get_node_value(items[1]) if len(items) > 1 else ''
            if is_in_new:
                if first_name not in c_obj.class_fields:
                    raise AttributeError(
                        f"La clase '{c_obj.name}' no tiene un atributo de clase '{first_name}'. "
                        f"No se pueden añadir nuevos atributos en tiempo de ejecución."
                    )
                curr_t = storage.resolve_type(c_obj.class_fields[first_name].type)
            else:
                if first_name not in c_obj.instance_fields:
                    raise AttributeError(
                        f"La clase '{c_obj.name}' no tiene un atributo de instancia '{first_name}'. "
                        f"No se pueden añadir nuevos atributos en tiempo de ejecución."
                    )
                curr_t = storage.resolve_type(c_obj.instance_fields[first_name].type)

            for it in items[2:]:
                field_name = get_node_value(it)
                curr_raw = curr_t.rstrip('*')
                if curr_raw in storage.classes:
                    sub_c = storage.classes[curr_raw]
                    if field_name not in sub_c.instance_fields:
                        raise AttributeError(f"La clase '{sub_c.name}' no tiene un atributo de instancia '{field_name}'.")
                    curr_t = storage.resolve_type(sub_c.instance_fields[field_name].type)
                elif curr_raw in storage.structs:
                    sub_s = storage.structs[curr_raw]
                    if field_name not in sub_s.field_map:
                        raise AttributeError(f"El struct '{curr_raw}' no tiene un campo '{field_name}'.")
                    curr_t = storage.resolve_type(sub_s.field_map[field_name].type)
                else:
                    raise TypeError(f"El tipo '{curr_raw}' no es una estructura o clase con campos.")

            target_type = curr_t
            last_member = get_node_value(items[-1])
            chain_obj = MemberAccess(target='self', member=last_member, in_scope=storage, inferred_type=target_type)

        # 2. Asignación sobre cls
        elif base_name == 'cls':
            cls_var = storage.resolve('cls')
            if cls_var is None:
                raise RuntimeError("Variable 'cls' no ha sido declarada.")
            cls_var.uses += 1
            raw_t = cls_var.type.rstrip('*')
            c_name = raw_t[:-6] if raw_t.endswith('_Class') else raw_t
            c_obj = storage.classes.get(c_name)
            if c_obj is None:
                raise RuntimeError(f"Clase '{c_name}' de 'cls' no encontrada.")

            first_name = get_node_value(items[1]) if len(items) > 1 else ''
            if first_name not in c_obj.class_fields:
                raise AttributeError(
                    f"La clase '{c_obj.name}' no tiene un atributo de clase '{first_name}'. "
                    f"No se pueden añadir nuevos atributos en tiempo de ejecución."
                )
            curr_t = storage.resolve_type(c_obj.class_fields[first_name].type)

            for it in items[2:]:
                field_name = get_node_value(it)
                curr_raw = curr_t.rstrip('*')
                if curr_raw in storage.classes:
                    sub_c = storage.classes[curr_raw]
                    if field_name not in sub_c.instance_fields:
                        raise AttributeError(f"La clase '{sub_c.name}' no tiene un atributo de instancia '{field_name}'.")
                    curr_t = storage.resolve_type(sub_c.instance_fields[field_name].type)
                elif curr_raw in storage.structs:
                    sub_s = storage.structs[curr_raw]
                    if field_name not in sub_s.field_map:
                        raise AttributeError(f"El struct '{curr_raw}' no tiene un campo '{field_name}'.")
                    curr_t = storage.resolve_type(sub_s.field_map[field_name].type)
                else:
                    raise TypeError(f"El tipo '{curr_raw}' no es una estructura o clase con campos.")

            target_type = curr_t
            last_member = get_node_value(items[-1])
            chain_obj = MemberAccess(target='cls', member=last_member, in_scope=storage, inferred_type=target_type)

        # 3. Asignación a atributo estático de clase: Clase.attr = val o Clase.sub.val = val
        elif (class_resolved := storage.classes.get(base_name) or storage.resolve(base_name)) and isinstance(class_resolved, ClassDecl):
            first_name = get_node_value(items[1]) if len(items) > 1 else ''
            if first_name not in class_resolved.class_fields:
                raise AttributeError(
                    f"La clase '{class_resolved.name}' no tiene un atributo de clase '{first_name}'. "
                    f"No se pueden añadir nuevos atributos en tiempo de ejecución."
                )
            curr_t = storage.resolve_type(class_resolved.class_fields[first_name].type)

            for it in items[2:]:
                field_name = get_node_value(it)
                curr_raw = curr_t.rstrip('*')
                if curr_raw in storage.classes:
                    sub_c = storage.classes[curr_raw]
                    if field_name not in sub_c.instance_fields:
                        raise AttributeError(f"La clase '{sub_c.name}' no tiene un atributo de instancia '{field_name}'.")
                    curr_t = storage.resolve_type(sub_c.instance_fields[field_name].type)
                elif curr_raw in storage.structs:
                    sub_s = storage.structs[curr_raw]
                    if field_name not in sub_s.field_map:
                        raise AttributeError(f"El struct '{curr_raw}' no tiene un campo '{field_name}'.")
                    curr_t = storage.resolve_type(sub_s.field_map[field_name].type)
                else:
                    raise TypeError(f"El tipo '{curr_raw}' no es una estructura o clase con campos.")

            target_type = curr_t
            last_member = get_node_value(items[-1])
            chain_obj = MemberAccess(target=base_name, member=last_member, in_scope=storage, inferred_type=target_type)

        # 4. Asignación sobre variable (instancia de clase, struct, etc.)
        else:
            base_obj = storage.resolve(base_name)
            if not isinstance(base_obj, (Variable, FunctionParam)):
                raise RuntimeError(f"Variable '{base_name}' no ha sido declarada.")
            if isinstance(base_obj, Variable) and base_obj.is_constant and base_name not in ('self', 'cls'):
                raise RuntimeError(f"No se puede modificar el miembro de la constante '{base_name}'.")
            base_obj.uses += 1

            curr_t = storage.resolve_type(base_obj.type)

            for it in items[1:]:
                field_name = get_node_value(it)
                curr_raw = curr_t.rstrip('*')
                if curr_raw in storage.classes:
                    sub_c = storage.classes[curr_raw]
                    if field_name not in sub_c.instance_fields:
                        raise AttributeError(
                            f"La clase '{sub_c.name}' no tiene un atributo de instancia '{field_name}'. "
                            f"No se pueden añadir nuevos atributos en tiempo de ejecución."
                        )
                    curr_t = storage.resolve_type(sub_c.instance_fields[field_name].type)
                elif curr_raw in storage.structs:
                    sub_s = storage.structs[curr_raw]
                    if field_name not in sub_s.field_map:
                        raise AttributeError(f"El struct '{curr_raw}' no tiene un campo '{field_name}'.")
                    curr_t = storage.resolve_type(sub_s.field_map[field_name].type)
                else:
                    raise TypeError(f"El tipo '{curr_raw}' de la variable '{base_name}' no es una estructura con campos.")

            target_type = curr_t
            last_member = get_node_value(items[-1])
            chain_obj = MemberAccess(target=base_name, member=last_member, in_scope=storage, inferred_type=target_type)

        if op == '=':
            if inferred is not None and target_type != 'any':
                validate_type(target_repr, target_type, inferred, storage=storage)
        else:
            validate_compound_assignment(target_repr, target_type, op, inferred, storage=storage)

        return Assign(target=chain_obj, value=value_node, op=op, in_scope=storage)

    # Caso 3: Asignación simple a variable
    else:
        var_name: str = get_node_value(target_node)
        if var_name in ('self', 'cls'):
            raise RuntimeError(f"No se puede reasignar '{var_name}'.")
        var_obj = storage.resolve(var_name)
        if not isinstance(var_obj, (Variable, FunctionParam)):
            raise RuntimeError(f"Variable '{var_name}' no ha sido declarada.")
        if isinstance(var_obj, Variable) and var_obj.is_constant:
            if var_obj.is_cptr:
                raise RuntimeError(f"No se puede reasignar el puntero constante '{var_name}'.")
            raise RuntimeError(f"No se puede reasignar la constante '{var_name}'.")

        if op == '=':
            if inferred is not None:
                validate_type(var_name, var_obj.type, inferred, storage=storage)
        else:
            if isinstance(var_obj, Variable) and var_obj.is_cptr:
                raise RuntimeError(f"No se puede reasignar el puntero constante '{var_name}'.")
            is_ptr = isinstance(var_obj, Variable) and var_obj.is_pointer
            validate_compound_assignment(var_name, var_obj.type, op, inferred, storage=storage, is_pointer=is_ptr)

        var_obj.value = value_node
        var_obj.uses += 1
        return Assign(target=var_name, value=value_node, op=op, in_scope=storage)



__all__ = [
    'COMPOUND_OPS',
    'validate_compound_assignment',
    'visit_assign',
]

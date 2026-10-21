from typing import Any

from gram import ast

from core.initiator.reserve_funnames import MagicFuncsManager
from core.processor.objects.call import Call
from core.processor.objects.class_decl import ClassDecl, ClassField, ClassMethod
from core.processor.objects.enum_decl import EnumDecl
from core.processor.objects.expression import IndexAccess
from core.processor.objects.function import Function, FunctionParam, LocalStorage
from core.processor.objects.member_access import MemberAccess
from core.processor.objects.method_call import MethodCall, SuperInitCall
from core.processor.objects.struct_decl import StructDecl, StructField
from core.processor.objects.variable import Variable
from core.processor.visitors.utils import (
    extract_chain_items,
    extract_constant_int,
    get_node_value,
    parse_array_type,
)


def extract_call_args(call_node: Any) -> tuple[list[Any], dict[str, Any]]:
    pos_args: list[Any] = []
    kw_args: dict[str, Any] = {}
    if not call_node:
        return pos_args, kw_args

    if isinstance(call_node, ast.ASTRef) and len(call_node.nodes) >= 2:
        args_node = call_node.nodes[1]
        if isinstance(args_node, ast.ASTRef) and args_node.nodes:
            first = args_node.nodes[0]
            items = first.items if isinstance(first, ast.ArrayNode) else args_node.nodes
            for item in items:
                pos_args.append(item)
        return pos_args, kw_args

    return pos_args, kw_args


def _validate_call_arguments(
    storage: Any,
    callee_name: str,
    parameters: list[FunctionParam],
    args: list[Any],
    callee_kind: str = "La función",
) -> None:
    min_args = sum(1 for p in parameters if not p.has_default and not p.is_variadic)
    has_variadic = any(p.is_variadic for p in parameters)
    var_param = next((p for p in parameters if p.is_variadic), None)
    max_args = len(parameters)

    if len(args) < min_args or (not has_variadic and len(args) > max_args):
        expected = f"{min_args}" if min_args == max_args else f"entre {min_args} y {max_args}"
        raise TypeError(
            f"{callee_kind} '{callee_name}' espera {expected} argumentos, pero se recibieron {len(args)}."
        )

    from core.processor.visitors.var_decl import infer_value_type, validate_type

    normal_params = [p for p in parameters if not p.is_variadic]
    for i, arg in enumerate(args):
        if i < len(normal_params):
            param = normal_params[i]
            inferred = infer_value_type(storage, arg)
            if inferred is not None and param.type and param.type not in ('any', 'ptr'):
                validate_type(param.name, param.type, inferred, storage=storage)
        elif var_param is not None:
            inferred = infer_value_type(storage, arg)
            if inferred is not None and var_param.type and var_param.type not in ('any', 'ptr'):
                validate_type(var_param.name, var_param.type, inferred, storage=storage)



def _instantiate_class(storage: Any, class_obj: Any, args: list[Any], kwargs: dict[str, Any]) -> Call:
    call_obj = Call(name=class_obj.name, args=args, kwargs=kwargs, in_scope=storage)
    call_obj.returntype = class_obj.name
    call_obj.target_type = class_obj.name

    target_method = class_obj.init_method if (class_obj.init_method and class_obj.init_method.parameters) else class_obj.new_method
    params = target_method.parameters if target_method else []

    _validate_call_arguments(storage, class_obj.name, params, args, callee_kind="La clase")
    return call_obj


def _validate_method_arguments(storage: Any, method_obj: Any, args: list[Any]):
    _validate_call_arguments(storage, method_obj.name, method_obj.parameters, args, callee_kind="El método")


def visit_call(storage: Any, node: ast.ASTRef) -> Call:
    first_node = node.nodes[0]
    call_name: str = get_node_value(first_node)

    if call_name in ('__init__', '__new__'):
        raise RuntimeError(f"Los métodos mágicos intrínsecos '{call_name}' no pueden invocarse directamente.")

    if call_name == 'super':
        raise RuntimeError("'super()' no puede usarse de forma aislada; solo se permite como 'super().__init__()'.")

    args, kwargs = extract_call_args(node)
    call_obj = Call(name=call_name, args=args, kwargs=kwargs, in_scope=storage)

    # 1. Comprobar si es un símbolo en storage
    resolved = storage.resolve(call_name)

    if resolved is not None:
        if isinstance(resolved, Function):
            call_obj.returntype = resolved.return_type
            resolved.uses += 1

            # Validación de argumentos y tipos (CAL-01 / CAL-04)
            _validate_call_arguments(storage, call_name, resolved.parameters, args, callee_kind="La función")
            return call_obj

        if isinstance(resolved, ClassDecl):
            return _instantiate_class(storage, resolved, args, kwargs)

        if isinstance(resolved, StructDecl):
            call_obj.returntype = resolved.name
            return call_obj

        if isinstance(resolved, (Variable, FunctionParam)):
            raise TypeError(
                f"'{call_name}' es una variable/parámetro de tipo '{resolved.type}' y no se puede invocar como función."
            )

        if isinstance(resolved, EnumDecl):
            raise TypeError(
                f"'{call_name}' es un enum y no se puede invocar como función."
            )

        if isinstance(resolved, str):
            # Símbolo declarado vía import/include
            return call_obj

    # 2. Comprobar si es un struct o class constructor
    if call_name in storage.classes:
        return _instantiate_class(storage, storage.classes[call_name], args, kwargs)

    if call_name in storage.structs:
        call_obj.returntype = call_name
        return call_obj

    # 3. Comprobar declaraciones de import/include
    if call_name in storage.declarations:
        return call_obj

    # 4. Comprobar externs mediante el manager
    from core.externs.manager import manager

    extern_sym = manager.find_backend_symbol(call_name)
    if extern_sym:
        sym_info, header = extern_sym
        call_obj.returntype = sym_info.get('return_type', 'void')
        call_obj.is_pointer = (call_obj.returntype == 'ptr' or sym_info.get('is_pointer', False))
        return call_obj

    # 5. DE ÚLTIMO: Si no se encontró en el ámbito ni en externs, revisar reserve_funnames
    from core.initiator import reserve_funnames

    if reserve_funnames.exists(call_name):
        rf = reserve_funnames.MagicFuncsManager.get(call_name)
        call_obj.returntype = rf.returned if rf else 'void'
        return call_obj

    # 6. Si no se encontró en ninguna parte, lanzar error semántico
    raise RuntimeError(f"Función '{call_name}' no ha sido declarada.")


def visit_member_chain(storage: Any, node: ast.ASTRef) -> MethodCall | MemberAccess:
    items = extract_chain_items(node)
    if not items:
        return MemberAccess(target='', member='', in_scope=storage)

    # -------------------------------------------------------------------------
    # Detección y manejo estricto de 'super().__init__()' (Unión de Clases)
    # -------------------------------------------------------------------------
    first_item = items[0]
    is_super = False
    if isinstance(first_item, ast.ASTRef) and first_item.name == 'CALL':
        is_super = (get_node_value(first_item.nodes[0]) == 'super')
    elif isinstance(first_item, ast.ASTTokenNode):
        is_super = (first_item.token.value == 'super')

    if is_super:
        if not (isinstance(first_item, ast.ASTRef) and first_item.name == 'CALL'):
            second_name = get_node_value(items[1]) if len(items) > 1 else ''
            if second_name:
                raise RuntimeError(
                    f"No se permite acceso a miembro 'super.{second_name}'. Easy-C utiliza unión de clases; 'super()' solo se permite como 'super().__init__()'."
                )
            raise RuntimeError("'super()' no puede usarse de forma aislada; solo se permite como 'super().__init__()'.")

        super_args, _ = extract_call_args(first_item)
        if super_args:
            raise RuntimeError("En Easy-C 'super()' no recibe argumentos; los argumentos deben pasarse a '__init__(...)' como 'super().__init__(...)'.")

        if len(items) < 2:
            raise RuntimeError("'super()' no puede usarse de forma aislada; solo se permite como 'super().__init__()'.")

        if len(items) > 2:
            raise RuntimeError("No se permite encadenar llamadas posteriores a 'super().__init__()'.")


        second_item = items[1]
        if not (isinstance(second_item, ast.ASTRef) and second_item.name == 'CALL'):
            member_name = get_node_value(second_item)
            raise RuntimeError(
                f"No se permite acceso a miembro 'super.{member_name}'. Easy-C utiliza unión de clases; 'super()' solo se permite como 'super().__init__()'."
            )

        called_method = get_node_value(second_item.nodes[0])
        if called_method != '__init__':
            raise RuntimeError(
                f"No se permite 'super().{called_method}()'. Easy-C utiliza unión de clases; 'super()' solo se permite como 'super().__init__()'."
            )

        # Validación de contexto: solo dentro de __init__ de una clase
        if not isinstance(storage, LocalStorage):
            raise RuntimeError("'super().__init__()' solo puede invocarse dentro del método '__init__' de una clase.")

        func = storage.function
        if not isinstance(func, ClassMethod) or func.name != '__init__':
            raise RuntimeError("'super().__init__()' solo puede invocarse dentro del método '__init__' de una clase.")

        class_obj = func.class_decl
        if not isinstance(class_obj, ClassDecl) or not class_obj.bases:
            cls_name = class_obj.name if isinstance(class_obj, ClassDecl) else 'desconocida'
            raise RuntimeError(f"La clase '{cls_name}' no hereda de ninguna clase base para invocar 'super().__init__()'.")

        if func.has_super_init:
            raise RuntimeError(f"Llamada duplicada a 'super().__init__()' en la clase '{class_obj.name}'.")

        # Localizar la clase base primaria y validar argumentos contra su __init__
        primary_base_name = class_obj.bases[0]
        global_storage = storage.parent if isinstance(storage, LocalStorage) else storage
        base_class = global_storage.classes.get(primary_base_name) or global_storage.resolve(primary_base_name)
        if not isinstance(base_class, ClassDecl):
            raise RuntimeError(f"Clase base '{primary_base_name}' no encontrada para la clase '{class_obj.name}'.")

        base_init = base_class.init_method or base_class.methods.get('__init__')
        args, kwargs = extract_call_args(second_item)

        if base_init is not None:
            _validate_call_arguments(storage, f"{base_class.name}.__init__", base_init.parameters, args, callee_kind="El método")

        # Unión de clases: unificar campos de instancia de las clases base en la subclase
        for base_name in class_obj.bases:
            b_obj = global_storage.classes.get(base_name) or global_storage.resolve(base_name)
            if isinstance(b_obj, ClassDecl):
                for f_name, f_field in b_obj.instance_fields.items():
                    if f_name not in class_obj.instance_fields:
                        class_obj.instance_fields[f_name] = f_field

        func.has_super_init = True

        return SuperInitCall(
            base_class=primary_base_name,
            args=args,
            kwargs=kwargs,
            in_scope=storage,
        )

    # CAL-02: Detección y organización jerárquica de llamadas encadenadas (Fluent Interface)
    has_intermediate_call = any(
        isinstance(it, ast.ASTRef) and it.name == 'CALL'
        for it in items[:-1]
    ) or (items and isinstance(items[0], ast.ASTRef) and items[0].name == 'CALL')


    if has_intermediate_call:
        current_target: Any = None
        id_prefix: list[str] = []

        for item in items:
            if isinstance(item, ast.ASTRef) and item.name == 'CALL':
                call_name = get_node_value(item.nodes[0])
                if call_name in ('__init__', '__new__'):
                    raise RuntimeError(f"Los métodos mágicos intrínsecos '{call_name}' no pueden invocarse directamente.")
                args, kwargs = extract_call_args(item)
                if current_target is None:
                    if id_prefix:
                        target_str = '.'.join(id_prefix)
                        current_target = MethodCall(target=target_str, method=call_name, args=args, kwargs=kwargs, in_scope=storage)
                        id_prefix = []
                    else:
                        current_target = Call(name=call_name, args=args, kwargs=kwargs, in_scope=storage)
                else:
                    if id_prefix:
                        for part in id_prefix:
                            current_target = MemberAccess(target=current_target, member=part, in_scope=storage)
                        id_prefix = []
                    current_target = MethodCall(target=current_target, method=call_name, args=args, kwargs=kwargs, in_scope=storage)
            else:
                val = get_node_value(item)
                if current_target is None:
                    id_prefix.append(val)
                else:
                    current_target = MemberAccess(target=current_target, member=val, in_scope=storage)

        if id_prefix and current_target is not None:
            for part in id_prefix:
                current_target = MemberAccess(target=current_target, member=part, in_scope=storage)

        return current_target

    last_item = items[-1]

    if isinstance(last_item, ast.ASTRef) and last_item.name == 'CALL':
        # Es una llamada a método (e.g. std.io.println("..."), obj.metodo(1, 2))
        first_call_node = last_item.nodes[0]
        method_name = get_node_value(first_call_node)

        if method_name in ('__init__', '__new__'):
            raise RuntimeError(f"Los métodos mágicos intrínsecos '{method_name}' no pueden invocarse directamente.")

        args, kwargs = extract_call_args(last_item)

        target_parts = [get_node_value(it) for it in items[:-1]]
        target = '.'.join(target_parts)

        call_obj = MethodCall(target=target, method=method_name, args=args, kwargs=kwargs, in_scope=storage)

        from core.externs.manager import manager

        if manager.has_namespace(target):
            sym_info = manager.validate_call(target, method_name, args)
            call_obj.returntype = sym_info.get('return_type', 'void')
            return call_obj

        # 1. Comprobar si el objetivo es directamente una clase (llamada de clase o estática)
        class_resolved = storage.classes.get(target) or storage.resolve(target)
        if isinstance(class_resolved, ClassDecl):
            if method_name in class_resolved.instance_methods:
                raise AttributeError(
                    f"El método de instancia '{method_name}' de la clase '{class_resolved.name}' requiere una instancia para ser invocado."
                )
            method_obj = class_resolved.class_methods.get(method_name) or class_resolved.static_methods.get(method_name)
            if method_obj is None:
                raise AttributeError(f"La clase '{class_resolved.name}' no tiene un método '{method_name}'.")
            _validate_method_arguments(storage, method_obj, args)
            call_obj.returntype = method_obj.return_type
            return call_obj

        # 2. Comprobar si target es 'self'
        if target_parts and target_parts[0] == 'self':
            self_var = storage.resolve('self')
            if self_var is None:
                raise RuntimeError("Variable 'self' no ha sido declarada.")
            self_var.uses += 1
            raw_t = self_var.type.rstrip('*')
            is_in_new = raw_t.endswith('_Class')
            c_name = raw_t[:-6] if is_in_new else raw_t
            c_obj = storage.classes.get(c_name)
            if c_obj is not None:
                if is_in_new:
                    # En __new__: self es alias de cls
                    if method_name in c_obj.instance_methods:
                        raise AttributeError(
                            f"El método de instancia '{method_name}' de la clase '{c_obj.name}' requiere una instancia para ser invocado."
                        )
                    method_obj = c_obj.class_methods.get(method_name) or c_obj.static_methods.get(method_name)
                    if method_obj is None:
                        raise AttributeError(f"La clase '{c_obj.name}' no tiene un método '{method_name}'.")
                    _validate_method_arguments(storage, method_obj, args)
                    call_obj.returntype = method_obj.return_type
                    return call_obj
                else:
                    # En método de instancia o __init__
                    if method_name in c_obj.class_methods:
                        raise AttributeError(
                            f"El método de clase '{method_name}' de '{c_obj.name}' no se puede invocar desde una instancia; debe llamarse como '{c_obj.name}.{method_name}'."
                        )
                    if method_name in c_obj.static_methods:
                        raise AttributeError(
                            f"El método estático '{method_name}' de '{c_obj.name}' debe llamarse desde la clase '{c_obj.name}.{method_name}'."
                        )
                    method_obj = c_obj.instance_methods.get(method_name)
                    if method_obj is None:
                        raise AttributeError(f"La clase '{c_obj.name}' no tiene un método de instancia '{method_name}'.")
                    _validate_method_arguments(storage, method_obj, args)
                    call_obj.returntype = method_obj.return_type
                    return call_obj

        # 3. Comprobar si target es 'cls'
        if target_parts and target_parts[0] == 'cls':
            cls_var = storage.resolve('cls')
            if cls_var is None:
                raise RuntimeError("Variable 'cls' no ha sido declarada.")
            cls_var.uses += 1
            raw_t = cls_var.type.rstrip('*')
            c_name = raw_t[:-6] if raw_t.endswith('_Class') else raw_t
            c_obj = storage.classes.get(c_name)
            if c_obj is not None:
                if method_name in c_obj.instance_methods:
                    raise AttributeError(
                        f"El método de instancia '{method_name}' de la clase '{c_obj.name}' requiere una instancia para ser invocado."
                    )
                method_obj = c_obj.class_methods.get(method_name) or c_obj.static_methods.get(method_name)
                if method_obj is None:
                    raise AttributeError(f"La clase '{c_obj.name}' no tiene un método '{method_name}'.")
                _validate_method_arguments(storage, method_obj, args)
                call_obj.returntype = method_obj.return_type
                return call_obj

        # 4. Comprobar si target es una variable de instancia de clase
        if target_parts:
            base_name = target_parts[0]
            base_obj = storage.resolve(base_name)
            if isinstance(base_obj, (Variable, FunctionParam)):
                curr_t = storage.resolve_type(base_obj.type).rstrip('*')
                if curr_t in storage.classes:
                    c_obj = storage.classes[curr_t]
                    base_obj.uses += 1
                    if method_name in c_obj.class_methods:
                        raise AttributeError(
                            f"El método de clase '{method_name}' de '{c_obj.name}' no se puede invocar desde una instancia; debe llamarse como '{c_obj.name}.{method_name}'."
                        )
                    if method_name in c_obj.static_methods:
                        raise AttributeError(
                            f"El método estático '{method_name}' de '{c_obj.name}' debe llamarse desde la clase '{c_obj.name}.{method_name}'."
                        )
                    method_obj = c_obj.instance_methods.get(method_name)
                    if method_obj is None:
                        raise AttributeError(f"La clase '{c_obj.name}' no tiene un método de instancia '{method_name}'.")
                    _validate_method_arguments(storage, method_obj, args)
                    call_obj.returntype = method_obj.return_type
                    return call_obj

        return call_obj

    else:
        # Es un acceso a miembro (e.g. point.x, std.math.PI)
        member_name = get_node_value(last_item)
        target_parts = [get_node_value(it) for it in items[:-1]]
        target = '.'.join(target_parts)

        # 1. Comprobar si target es directamente una clase
        class_resolved = storage.classes.get(target_parts[0]) or storage.resolve(target_parts[0]) if target_parts else None
        if isinstance(class_resolved, ClassDecl):
            if len(target_parts) == 1:
                if member_name in class_resolved.class_fields:
                    field = class_resolved.class_fields[member_name]
                    return MemberAccess(target=target, member=member_name, in_scope=storage, inferred_type=field.type)
                if member_name in class_resolved.instance_fields:
                    raise AttributeError(
                        f"El atributo de instancia '{member_name}' de la clase '{class_resolved.name}' no puede accederse desde la clase."
                    )
                raise AttributeError(f"La clase '{class_resolved.name}' no tiene un atributo de clase '{member_name}'.")
            else:
                first_part = target_parts[1]
                if first_part not in class_resolved.class_fields:
                    raise AttributeError(f"La clase '{class_resolved.name}' no tiene un atributo de clase '{first_part}'.")
                curr_t = storage.resolve_type(class_resolved.class_fields[first_part].type).rstrip('*')
                for part in target_parts[2:]:
                    if curr_t in storage.structs:
                        struct_obj = storage.structs[curr_t]
                        if part in struct_obj.field_map:
                            curr_t = storage.resolve_type(struct_obj.field_map[part].type).rstrip('*')
                        else:
                            raise AttributeError(f"El struct '{curr_t}' no tiene un campo '{part}'.")
                    elif curr_t in storage.classes:
                        sub_c = storage.classes[curr_t]
                        if part in sub_c.instance_fields:
                            curr_t = storage.resolve_type(sub_c.instance_fields[part].type).rstrip('*')
                        else:
                            raise AttributeError(f"La clase '{curr_t}' no tiene un atributo de instancia '{part}'.")
                    else:
                        raise AttributeError(f"El tipo '{curr_t}' no tiene un campo '{part}'.")

                if curr_t in storage.classes:
                    sub_c = storage.classes[curr_t]
                    if member_name in sub_c.instance_fields:
                        return MemberAccess(target=target, member=member_name, in_scope=storage, inferred_type=sub_c.instance_fields[member_name].type)
                    raise AttributeError(f"La clase '{sub_c.name}' no tiene un atributo de instancia '{member_name}'.")
                elif curr_t in storage.structs:
                    sub_s = storage.structs[curr_t]
                    if member_name in sub_s.field_map:
                        return MemberAccess(target=target, member=member_name, in_scope=storage, inferred_type=storage.resolve_type(sub_s.field_map[member_name].type))
                    raise AttributeError(f"El struct '{curr_t}' no tiene un campo '{member_name}'.")
                else:
                    raise AttributeError(f"El tipo '{curr_t}' no tiene un campo '{member_name}'.")

        # 1b. Comprobar si target es directamente un struct, mold o flags (no se permite acceder a campos de instancia sin instanciar)
        struct_resolved = (
            storage.find_struct(target_parts[0])
            or storage.structs.get(target_parts[0])
            or (storage.resolve(target_parts[0]) if target_parts else None)
        )
        if isinstance(struct_resolved, StructDecl):
            if len(target_parts) == 1:
                if member_name in struct_resolved.field_map:
                    raise AttributeError(
                        f"El campo de instancia '{member_name}' del {struct_resolved.kind} '{struct_resolved.name}' "
                        f"requiere una instancia para ser accedido."
                    )
                raise AttributeError(f"El {struct_resolved.kind} '{struct_resolved.name}' no tiene un campo '{member_name}'.")
            raise AttributeError(
                f"El {struct_resolved.kind} '{struct_resolved.name}' no permite acceso a miembros directamente desde el tipo."
            )

        # 1c. Comprobar si target es directamente un enum (Enum.MEMBER es válido)
        enum_resolved = (
            storage.find_enum(target_parts[0])
            or storage.enums.get(target_parts[0])
            or (storage.resolve(target_parts[0]) if target_parts else None)
        )
        if isinstance(enum_resolved, EnumDecl):
            if len(target_parts) == 1:
                if member_name in enum_resolved.members:
                    return MemberAccess(target=target, member=member_name, in_scope=storage, inferred_type=enum_resolved.name)
                raise AttributeError(f"El enum '{enum_resolved.name}' no tiene un miembro '{member_name}'.")
            raise AttributeError(
                f"No se permite encadenar accesos adicionales sobre el miembro '{member_name}' del enum '{enum_resolved.name}'."
            )

        # 2. Comprobar si target es 'self'
        if target_parts and target_parts[0] == 'self':
            self_var = storage.resolve('self')
            if self_var is None:
                raise RuntimeError("Variable 'self' no ha sido declarada.")
            self_var.uses += 1
            raw_t = self_var.type.rstrip('*')
            is_in_new = raw_t.endswith('_Class')
            c_name = raw_t[:-6] if is_in_new else raw_t
            c_obj = storage.classes.get(c_name)
            if c_obj is not None:
                if len(target_parts) == 1:
                    if is_in_new:
                        if member_name in c_obj.class_fields:
                            field = c_obj.class_fields[member_name]
                            return MemberAccess(target=target, member=member_name, in_scope=storage, inferred_type=field.type)
                        raise AttributeError(f"La clase '{c_obj.name}' no tiene un atributo de clase '{member_name}'.")
                    else:
                        if member_name in c_obj.instance_fields:
                            field = c_obj.instance_fields[member_name]
                            return MemberAccess(target=target, member=member_name, in_scope=storage, inferred_type=field.type)
                        if member_name in c_obj.class_fields:
                            raise AttributeError(f"El atributo de clase '{member_name}' de '{c_obj.name}' debe accederse desde la clase, no desde una instancia.")
                        raise AttributeError(f"La clase '{c_obj.name}' no tiene un atributo de instancia '{member_name}'.")
                else:
                    first_part = target_parts[1]
                    field_obj = c_obj.class_fields.get(first_part) if is_in_new else c_obj.instance_fields.get(first_part)
                    if field_obj is None:
                        raise AttributeError(f"La clase '{c_obj.name}' no tiene un atributo '{first_part}'.")
                    curr_t = storage.resolve_type(field_obj.type).rstrip('*')
                    for part in target_parts[2:]:
                        if curr_t in storage.structs:
                            struct_obj = storage.structs[curr_t]
                            if part in struct_obj.field_map:
                                curr_t = storage.resolve_type(struct_obj.field_map[part].type).rstrip('*')
                            else:
                                raise AttributeError(f"El struct '{curr_t}' no tiene un campo '{part}'.")
                        elif curr_t in storage.classes:
                            sub_c = storage.classes[curr_t]
                            if part in sub_c.instance_fields:
                                curr_t = storage.resolve_type(sub_c.instance_fields[part].type).rstrip('*')
                            else:
                                raise AttributeError(f"La clase '{curr_t}' no tiene un atributo de instancia '{part}'.")
                        else:
                            raise AttributeError(f"El tipo '{curr_t}' no tiene un campo '{part}'.")

                    if curr_t in storage.classes:
                        sub_c = storage.classes[curr_t]
                        if member_name in sub_c.instance_fields:
                            return MemberAccess(target=target, member=member_name, in_scope=storage, inferred_type=sub_c.instance_fields[member_name].type)
                        raise AttributeError(f"La clase '{sub_c.name}' no tiene un atributo de instancia '{member_name}'.")
                    elif curr_t in storage.structs:
                        sub_s = storage.structs[curr_t]
                        if member_name in sub_s.field_map:
                            return MemberAccess(target=target, member=member_name, in_scope=storage, inferred_type=storage.resolve_type(sub_s.field_map[member_name].type))
                        raise AttributeError(f"El struct '{curr_t}' no tiene un campo '{member_name}'.")
                    else:
                        raise AttributeError(f"El tipo '{curr_t}' no tiene un campo '{member_name}'.")

        # 3. Comprobar si target es 'cls'
        if target_parts and target_parts[0] == 'cls':
            cls_var = storage.resolve('cls')
            if cls_var is None:
                raise RuntimeError("Variable 'cls' no ha sido declarada.")
            cls_var.uses += 1
            raw_t = cls_var.type.rstrip('*')
            c_name = raw_t[:-6] if raw_t.endswith('_Class') else raw_t
            c_obj = storage.classes.get(c_name)
            if c_obj is not None:
                if len(target_parts) == 1:
                    if member_name in c_obj.class_fields:
                        field = c_obj.class_fields[member_name]
                        return MemberAccess(target=target, member=member_name, in_scope=storage, inferred_type=field.type)
                    raise AttributeError(f"La clase '{c_obj.name}' no tiene un atributo de clase '{member_name}'.")
                else:
                    first_part = target_parts[1]
                    if first_part not in c_obj.class_fields:
                        raise AttributeError(f"La clase '{c_obj.name}' no tiene un atributo de clase '{first_part}'.")
                    curr_t = storage.resolve_type(c_obj.class_fields[first_part].type).rstrip('*')
                    for part in target_parts[2:]:
                        if curr_t in storage.structs:
                            struct_obj = storage.structs[curr_t]
                            if part in struct_obj.field_map:
                                curr_t = storage.resolve_type(struct_obj.field_map[part].type).rstrip('*')
                            else:
                                raise AttributeError(f"El struct '{curr_t}' no tiene un campo '{part}'.")
                        elif curr_t in storage.classes:
                            sub_c = storage.classes[curr_t]
                            if part in sub_c.instance_fields:
                                curr_t = storage.resolve_type(sub_c.instance_fields[part].type).rstrip('*')
                            else:
                                raise AttributeError(f"La clase '{curr_t}' no tiene un atributo de instancia '{part}'.")
                        else:
                            raise AttributeError(f"El tipo '{curr_t}' no tiene un campo '{part}'.")

                    if curr_t in storage.classes:
                        sub_c = storage.classes[curr_t]
                        if member_name in sub_c.instance_fields:
                            return MemberAccess(target=target, member=member_name, in_scope=storage, inferred_type=sub_c.instance_fields[member_name].type)
                        raise AttributeError(f"La clase '{sub_c.name}' no tiene un atributo de instancia '{member_name}'.")
                    elif curr_t in storage.structs:
                        sub_s = storage.structs[curr_t]
                        if member_name in sub_s.field_map:
                            return MemberAccess(target=target, member=member_name, in_scope=storage, inferred_type=storage.resolve_type(sub_s.field_map[member_name].type))
                        raise AttributeError(f"El struct '{curr_t}' no tiene un campo '{member_name}'.")
                    else:
                        raise AttributeError(f"El tipo '{curr_t}' no tiene un campo '{member_name}'.")

        # 4. Comprobar si target es una variable (instancia de clase o struct)
        if target_parts:
            base_name = target_parts[0]
            base_obj = storage.resolve(base_name)
            if isinstance(base_obj, (Variable, FunctionParam)):
                curr_t = storage.resolve_type(base_obj.type).rstrip('*')

                # Recorrer partes intermedias de la cadena (ej: o.inner.val -> recorrer inner)
                for part in target_parts[1:]:
                    if curr_t in storage.structs:
                        struct_obj = storage.structs[curr_t]
                        if part in struct_obj.field_map:
                            field = struct_obj.field_map[part]
                            curr_t = storage.resolve_type(field.type).rstrip('*')
                        else:
                            raise AttributeError(f"El struct '{curr_t}' no tiene un campo '{part}'.")
                    elif curr_t in storage.classes:
                        c_obj = storage.classes[curr_t]
                        if part in c_obj.instance_fields:
                            field = c_obj.instance_fields[part]
                            curr_t = storage.resolve_type(field.type).rstrip('*')
                        else:
                            raise AttributeError(f"La clase '{curr_t}' no tiene un atributo de instancia '{part}'.")
                    else:
                        raise AttributeError(f"El tipo '{curr_t}' no tiene un campo '{part}'.")

                if curr_t in storage.classes:
                    c_obj = storage.classes[curr_t]
                    base_obj.uses += 1
                    if member_name in c_obj.instance_fields:
                        field = c_obj.instance_fields[member_name]
                        return MemberAccess(target=target, member=member_name, in_scope=storage, inferred_type=field.type)
                    if member_name in c_obj.class_fields:
                        raise AttributeError(f"El atributo de clase '{member_name}' de '{c_obj.name}' debe accederse desde la clase, no desde una instancia.")
                    raise AttributeError(f"La clase '{c_obj.name}' no tiene un atributo de instancia '{member_name}'.")

                struct_obj = storage.find_struct(curr_t) or storage.structs.get(curr_t)
                if struct_obj is not None:
                    base_obj.uses += 1
                    if member_name in struct_obj.field_map:
                        field = struct_obj.field_map[member_name]
                        f_type = storage.resolve_type(field.type)
                        return MemberAccess(target=target, member=member_name, in_scope=storage, inferred_type=f_type)
                    else:
                        raise AttributeError(f"El {struct_obj.kind} '{curr_t}' no tiene un campo '{member_name}'.")

        return MemberAccess(target=target, member=member_name, in_scope=storage)


def visit_index_access(storage: Any, node: ast.ASTRef) -> IndexAccess:
    target_node = node.nodes[0]
    target_result: Any = None
    target_type: str = 'any'
    target_name: str = ''

    # 1. Resolver el objetivo indexado
    if isinstance(target_node, ast.ASTTokenNode):
        var_name = target_node.token.value
        var_obj = storage.resolve(var_name)
        if var_obj is None:
            raise RuntimeError(f"Variable '{var_name}' no ha sido declarada.")
        if not isinstance(var_obj, (Variable, FunctionParam)):
            raise TypeError(f"'{var_name}' no es una variable indexable.")
        target_type = storage.resolve_type(var_obj.type)
        target_name = var_name
        var_obj.uses += 1
        target_result = var_obj

    elif isinstance(target_node, ast.ASTRef) and target_node.name == 'MEMBER_CHAIN':
        target_result = visit_member_chain(storage, target_node)
        items = extract_chain_items(target_node)
        if not items:
            raise RuntimeError("Cadena de miembros vacía.")
        base_name = get_node_value(items[0])
        base_obj = storage.resolve(base_name)
        if base_obj is None:
            from core.externs.manager import manager
            target_str = '.'.join(get_node_value(it) for it in items)
            if manager.has_namespace(target_str):
                target_type = 'any'
            else:
                raise RuntimeError(f"Variable '{base_name}' no ha sido declarada.")
        else:
            curr_t = storage.resolve_type(base_obj.type)
            base_obj.uses += 1
            for it in items[1:]:
                field_name = get_node_value(it)
                if curr_t not in storage.structs:
                    raise TypeError(f"El tipo '{curr_t}' de la variable '{base_name}' no es indexable.")
                struct_obj = storage.structs[curr_t]
                if field_name not in struct_obj.field_map:
                    raise AttributeError(f"El struct '{curr_t}' no tiene un campo '{field_name}'.")
                curr_t = storage.resolve_type(struct_obj.field_map[field_name].type)
            target_type = curr_t
        target_name = '.'.join(get_node_value(it) for it in items)

    elif isinstance(target_node, ast.ASTRef) and target_node.name == 'CALL':
        target_result = visit_call(storage, target_node)
        target_type = target_result.returntype or 'void'
        if target_type == 'void':
            raise TypeError("No se puede indexar una llamada que retorna 'void'.")
        target_name = f"{target_result.name}()"

    elif isinstance(target_node, ast.ASTRef) and target_node.name == 'INDEX_ACCESS':
        target_result = visit_index_access(storage, target_node)
        target_type = target_result.inferred_type or 'any'
        target_name = str(target_result)

    else:
        target_name = str(target_node)
        target_type = 'any'
        target_result = target_node

    # 2. Procesar índices y desenvolver tipos
    raw_indices = node.nodes[1] if len(node.nodes) > 1 and isinstance(node.nodes[1], list) else ([node.nodes[1]] if len(node.nodes) > 1 else [])
    from core.processor.visitors.var_decl import INTEGER_TYPES, STRING_TYPES, infer_value_type

    current_type = target_type
    for idx_expr in raw_indices:
        idx_inferred = infer_value_type(storage, idx_expr)
        if idx_inferred is not None:
            res_idx_t = storage.resolve_type(idx_inferred)
            if res_idx_t not in INTEGER_TYPES:
                raise TypeError(f"El índice debe ser de tipo entero, pero se recibió '{idx_inferred}'.")

        res_curr_t = storage.resolve_type(current_type)
        if res_curr_t.startswith('array[') and res_curr_t.endswith(']'):
            elem_t, static_size = parse_array_type(res_curr_t)
            if static_size is None and isinstance(target_result, (Variable, StructField, ClassField)):
                static_size = target_result.fixed_size

            if static_size is not None:
                idx_const = extract_constant_int(idx_expr)
                if idx_const is not None:
                    if idx_const < 0:
                        raise IndexError(f"Índice negativo {idx_const} no permitido para arreglo de tamaño {static_size}.")
                    if idx_const >= static_size:
                        raise IndexError(
                            f"Índice {idx_const} fuera de rango para arreglo de tamaño {static_size} (rango válido: 0 a {static_size - 1})."
                        )
            current_type = elem_t
        elif res_curr_t in STRING_TYPES:
            current_type = 'char'
        elif res_curr_t in ('ptr', 'cptr', 'any') or (isinstance(target_result, Variable) and target_result.is_pointer):
            current_type = 'any' if res_curr_t == 'void' else res_curr_t

        else:
            raise TypeError(f"El tipo '{res_curr_t}' de la variable '{target_name}' no es indexable.")

    return IndexAccess(
        target=target_result,
        index=raw_indices[0] if raw_indices else None,
        indices=raw_indices,
        in_scope=storage,
        inferred_type=current_type,
    )


__all__ = [
    'extract_call_args',
    'visit_call',
    'visit_index_access',
    'visit_member_chain',
]

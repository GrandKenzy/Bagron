from typing import Any
from gram import ast
from core.processor.objects.class_decl import ClassDecl, ClassField, ClassMethod
from core.processor.objects.function import LocalStorage
from core.processor.objects.variable import Variable
from core.processor.storage import Storage
from core.processor.visitors.func_decl import process_parameters
from core.processor.visitors.utils import extract_chain_items, get_node_value
from core.processor.visitors.var_decl import (
    _extract_ptr_modifier,
    extract_type,
    infer_value_type,
    validate_type,
)


def _validate_staticmethod_no_self_cls(node: Any, method_name: str):
    """Verifica recursivamente que no se use 'self' ni 'cls' en un método estático."""
    if isinstance(node, ast.ASTTokenNode):
        if node.token.value in ('self', 'cls'):
            raise RuntimeError(f"No se puede usar '{node.token.value}' dentro del método estático '{method_name}'.")
    elif isinstance(node, ast.ASTRef):
        for child in node.nodes:
            _validate_staticmethod_no_self_cls(child, method_name)
    elif isinstance(node, ast.ArrayNode):
        for child in node.items:
            _validate_staticmethod_no_self_cls(child, method_name)
    elif isinstance(node, list):
        for child in node:
            _validate_staticmethod_no_self_cls(child, method_name)


def _process_method_body(
    local_storage: LocalStorage,
    method: ClassMethod,
    class_obj: ClassDecl,
    body_node: ast.ASTRef,
    inherited_from: dict[str, str] | None = None,
) -> list[Any]:
    statements = body_node.nodes[1] if len(body_node.nodes) > 1 and isinstance(body_node.nodes[1], list) else []
    processed_body: list[Any] = []

    from core.processor.visitors.assign import visit_assign
    from core.processor.visitors.var_decl import visit_var

    for child in statements:
        if isinstance(child, ast.ASTKeyword):
            if child.token.value == 'pass':
                processed_body.append(child)
                continue

        if isinstance(child, ast.ASTRef):
            if child.name == 'RETURN':
                has_value = len(child.nodes) > 1 and child.nodes[1] is not None
                if method.return_type == 'void' and has_value:
                    raise RuntimeError(f"El método '{method.name}' de tipo 'void' no puede retornar un valor.")
                if method.return_type != 'void' and not has_value:
                    raise RuntimeError(f"El método '{method.name}' de tipo '{method.return_type}' debe retornar un valor, no void.")
                if has_value:
                    inferred = infer_value_type(local_storage, child.nodes[1])
                    if inferred is not None:
                        validate_type(method.name, method.return_type, inferred, storage=local_storage)
                processed_body.append(child)

            elif child.name == 'VAR_DECL':
                decl = child.nodes[-1]
                ptr_mod, start_idx = _extract_ptr_modifier(decl)
                target_node = decl.nodes[start_idx]
                if isinstance(target_node, ast.ASTRef) and target_node.name == 'MEMBER_CHAIN':
                    items = extract_chain_items(target_node)
                    if items:
                        base_name = get_node_value(items[0])
                        field_name = get_node_value(items[1]) if len(items) > 1 else ''
                        if decl.name in ('VAR_FULL_DECL', 'VAR_PARTIAL_DECL'):
                            type_node = decl.nodes[start_idx + 2]
                            var_type = ptr_mod if ptr_mod else extract_type(type_node)
                            val_node = decl.nodes[start_idx + 4] if decl.name == 'VAR_FULL_DECL' and len(decl.nodes) > start_idx + 4 else None
                        elif decl.name == 'VAR_PTR_GENERIC_DECL':
                            var_type = ptr_mod or 'ptr'
                            val_node = decl.nodes[start_idx + 2] if len(decl.nodes) > start_idx + 2 else None
                        else:  # VAR_PTR_GENERIC_PARTIAL
                            var_type = ptr_mod or 'ptr'
                            val_node = None

                        if base_name in ('self', 'cls') and method.kind == 'staticmethod':
                            raise RuntimeError(f"No se puede usar '{base_name}' dentro del método estático '{method.name}'.")

                        if base_name == 'self' and method.name == '__init__':
                            class_obj.instance_fields[field_name] = ClassField(
                                name=field_name,
                                type=var_type,
                                value=val_node,
                                is_static=False,
                            )
                        elif base_name in ('cls', 'self') and method.name == '__new__':
                            class_obj.class_fields[field_name] = ClassField(
                                name=field_name,
                                type=var_type,
                                value=val_node,
                                is_static=True,
                            )
                        elif base_name == 'self' and method.kind == 'instance':
                            if field_name not in class_obj.instance_fields:
                                raise AttributeError(
                                    f"La clase '{class_obj.name}' no tiene un atributo de instancia '{field_name}'. "
                                    f"No se pueden añadir nuevos atributos en tiempo de ejecución."
                                )
                        elif base_name == 'cls' and method.kind == 'classmethod':
                            if field_name not in class_obj.class_fields:
                                raise AttributeError(
                                    f"La clase '{class_obj.name}' no tiene un atributo de clase '{field_name}'. "
                                    f"No se pueden añadir nuevos atributos en tiempo de ejecución."
                                )

                var_obj = visit_var(local_storage, child)
                if isinstance(var_obj, list):
                    processed_body.extend(var_obj)
                else:
                    processed_body.append(var_obj)

            elif child.name == 'VAR_ASSIGNATION':
                target_node = child.nodes[0]
                if isinstance(target_node, ast.ASTRef) and target_node.name == 'ASSIGN_TARGET':
                    target_node = target_node.nodes[0]

                # Detección de auto-declaración de atributos en __init__ y __new__
                if isinstance(target_node, ast.ASTRef) and target_node.name == 'MEMBER_CHAIN':
                    items = extract_chain_items(target_node)
                    if items:
                        base_name = get_node_value(items[0])
                        field_name = get_node_value(items[1]) if len(items) > 1 else ''

                        if base_name in ('self', 'cls') and method.kind == 'staticmethod':
                            raise RuntimeError(f"No se puede usar '{base_name}' dentro del método estático '{method.name}'.")

                        # En __init__: self.x = valor registra el atributo de instancia
                        if base_name == 'self' and method.name == '__init__':
                            if field_name not in class_obj.instance_fields:
                                val_node = child.nodes[2] if len(child.nodes) > 2 else None
                                inferred = infer_value_type(local_storage, val_node) if val_node else 'any'
                                class_obj.instance_fields[field_name] = ClassField(
                                    name=field_name,
                                    type=inferred or 'any',
                                    is_static=False,
                                )
                            elif inherited_from and field_name in inherited_from:
                                pass


                        # En __new__: cls.x o self.x registra el atributo de clase
                        elif base_name in ('cls', 'self') and method.name == '__new__':
                            if field_name not in class_obj.class_fields:
                                val_node = child.nodes[2] if len(child.nodes) > 2 else None
                                inferred = infer_value_type(local_storage, val_node) if val_node else 'any'
                                class_obj.class_fields[field_name] = ClassField(
                                    name=field_name,
                                    type=inferred or 'any',
                                    is_static=True,
                                )

                        # En cualquier otro método: NO se permite monkey-patching
                        elif base_name == 'self' and method.kind == 'instance':
                            if field_name not in class_obj.instance_fields:
                                raise AttributeError(
                                    f"La clase '{class_obj.name}' no tiene un atributo de instancia '{field_name}'. "
                                    f"No se pueden añadir nuevos atributos en tiempo de ejecución."
                                )
                        elif base_name == 'cls' and method.kind == 'classmethod':
                            if field_name not in class_obj.class_fields:
                                raise AttributeError(
                                    f"La clase '{class_obj.name}' no tiene un atributo de clase '{field_name}'. "
                                    f"No se pueden añadir nuevos atributos en tiempo de ejecución."
                                )

                assign_obj = visit_assign(local_storage, child)
                processed_body.append(assign_obj)

            elif child.name == 'WHILE':
                from core.processor.visitors.while_statement import visit_while
                while_obj = visit_while(local_storage, child, in_loop=True, is_nested=True)
                processed_body.append(while_obj)

            elif child.name == 'FOR':
                from core.processor.visitors.for_statement import visit_for
                for_obj = visit_for(local_storage, child, is_nested=True)
                processed_body.append(for_obj)

            elif child.name == 'IF':
                from core.processor.visitors.if_statement import visit_if
                if_obj = visit_if(local_storage, child, in_loop=False, is_nested=True)
                processed_body.append(if_obj)

            elif child.name == 'CALL':
                from core.processor.visitors.call import visit_call
                call_obj = visit_call(local_storage, child)
                processed_body.append(call_obj)

            elif child.name == 'MEMBER_CHAIN':
                from core.processor.visitors.call import visit_member_chain
                chain_obj = visit_member_chain(local_storage, child)
                processed_body.append(chain_obj)

            elif child.name == 'INDEX_ACCESS':
                from core.processor.visitors.call import visit_index_access
                idx_obj = visit_index_access(local_storage, child)
                processed_body.append(idx_obj)

            else:
                processed_body.append(child)

    method.body = processed_body
    return processed_body


def _inherit_base_symbols(class_obj: ClassDecl, storage: Storage) -> dict[str, str]:
    """Hereda recursivamente campos y métodos de las clases base y retorna un mapa de símbolos heredados -> clase origen."""
    inherited_from: dict[str, str] = {}
    visited: set[str] = set()

    def walk(base_name: str):
        if base_name in visited:
            raise RuntimeError(f"Ciclo de herencia detectado: '{base_name}' en la clase '{class_obj.name}'.")
        visited.add(base_name)

        base_class = storage.classes.get(base_name) or storage.resolve(base_name)
        if not isinstance(base_class, ClassDecl):
            raise RuntimeError(f"Clase base '{base_name}' no declarada para la clase '{class_obj.name}'.")

        # Recursión sobre las bases de la clase base primero (orden ascendente)
        for grand_base in base_class.bases:
            walk(grand_base)

        # Heredar campos de instancia
        for f_name, f_obj in base_class.instance_fields.items():
            class_obj.instance_fields[f_name] = f_obj
            inherited_from[f_name] = base_class.name

        # Heredar campos de clase
        for f_name, f_obj in base_class.class_fields.items():
            class_obj.class_fields[f_name] = f_obj
            inherited_from[f_name] = base_class.name

        # Heredar métodos
        for m_name, m_obj in base_class.methods.items():
            if m_name == '__new__':
                continue
            class_obj.methods[m_name] = m_obj
            if m_obj.kind == 'instance':
                class_obj.instance_methods[m_name] = m_obj
            elif m_obj.kind == 'classmethod':
                class_obj.class_methods[m_name] = m_obj
            elif m_obj.kind == 'staticmethod':
                class_obj.static_methods[m_name] = m_obj

            if m_name == '__init__':
                class_obj.init_method = m_obj

            inherited_from[m_name] = base_class.name

    for base in class_obj.bases:
        walk(base)

    return inherited_from


def visit_class(storage: Storage, node: ast.ASTRef) -> ClassDecl:
    # 1. Desempaquetar CLASS_FIRM y CLASS_BODY

    firm_node = next(n for n in node.nodes if isinstance(n, ast.ASTRef) and n.name == 'CLASS_FIRM')
    body_node = next(n for n in node.nodes if isinstance(n, ast.ASTRef) and n.name == 'CLASS_BODY')

    # 2. Privacidad y nombre de la clase
    first_tok = firm_node.nodes[0]
    privacy: str = first_tok.token.value if isinstance(first_tok, ast.ASTTokenNode) and first_tok.token.value in ('public', 'private') else storage.privacy

    class_idx = -1
    for i, n in enumerate(firm_node.nodes):
        if isinstance(n, ast.ASTTokenNode) and n.token.value == 'class':
            class_idx = i
            break
    if class_idx == -1 or class_idx + 1 >= len(firm_node.nodes):
        raise SyntaxError("Declaración de clase inválida.")

    class_name: str = firm_node.nodes[class_idx + 1].token.value

    # 3. Comprobar colisiones globales
    storage.collition_name(class_name)

    # 4. Herencia
    bases: list[str] = []
    for n in firm_node.nodes:
        if isinstance(n, ast.ASTRef) and n.name == 'CLASS_HERENCY':
            items = n.nodes[0].items if n.nodes and isinstance(n.nodes[0], ast.ArrayNode) else (n.nodes[0] if n.nodes else [])
            for b in items:
                b_name = get_node_value(b)
                bases.append(b_name)

    # 5. Instanciar objeto ClassDecl y registrarlo en Storage
    class_obj = ClassDecl(
        name=class_name,
        privacy=privacy, # type: ignore
        bases=bases,
        in_scope=storage,
    )
    storage.add_class(class_name, class_obj)

    # 5b. Herencia recursiva de símbolos y contexto de las clases base (CAL-03)
    inherited_from = _inherit_base_symbols(class_obj, storage)
    local_class_fields: set[str] = set()
    local_methods: set[str] = set()

    # 6. Procesar miembros de CLASS_BODY
    items_list = body_node.nodes[1] if len(body_node.nodes) > 1 and isinstance(body_node.nodes[1], list) else []

    for item in items_list:
        if not isinstance(item, ast.ASTRef):
            continue

        # Variables de clase (estáticas) declaradas en el bloque de clase
        if item.name == 'VAR_DECL':
            decl = item.nodes[-1]
            ptr_mod, start_idx = _extract_ptr_modifier(decl)
            var_name: str = decl.nodes[start_idx].token.value
            if decl.name in ('VAR_FULL_DECL', 'VAR_PARTIAL_DECL'):
                type_node = decl.nodes[start_idx + 2]
                raw_type = extract_type(type_node)
                var_type = ptr_mod if ptr_mod else raw_type
                value_node = decl.nodes[start_idx + 4] if decl.name == 'VAR_FULL_DECL' else None
            elif decl.name == 'VAR_PTR_GENERIC_DECL':
                var_type = ptr_mod or 'ptr'
                value_node = decl.nodes[start_idx + 2]
            else:  # VAR_PTR_GENERIC_PARTIAL
                var_type = ptr_mod or 'ptr'
                value_node = None

            if var_name in ('self', 'cls'):
                raise RuntimeError(f"No se puede usar el identificador reservado '{var_name}' como nombre de variable en la clase '{class_name}'.")
            if var_name in local_class_fields:
                raise RuntimeError(f"Campo de clase duplicado '{var_name}' en la clase '{class_name}'.")
            local_class_fields.add(var_name)


            if value_node is not None:
                inferred = infer_value_type(storage, value_node)
                if inferred is not None:
                    validate_type(var_name, var_type, inferred, storage=storage)

            field_obj = ClassField(
                name=var_name,
                type=var_type,
                value=value_node,
                is_static=True,
                privacy=privacy,
            )
            class_obj.class_fields[var_name] = field_obj

        # Métodos de la clase
        elif item.name == 'CLASS_METHOD':
            dec_name = None
            func_node = None
            for sub in item.nodes:
                if isinstance(sub, ast.ASTRef):
                    if sub.name == 'DECORATOR':
                        dec_name = get_node_value(sub.nodes[1]) if len(sub.nodes) > 1 else None
                    elif sub.name == 'DECORATORS':
                        if sub.nodes and isinstance(sub.nodes[0], ast.ASTRef) and len(sub.nodes[0].nodes) > 1:
                            dec_name = get_node_value(sub.nodes[0].nodes[1])
                    elif sub.name == 'FUNCTION':
                        func_node = sub

            if func_node is None:
                func_node = item.nodes[-1]

            func_firm = func_node.nodes[0]
            func_body = func_node.nodes[1]

            method_name: str = func_firm.nodes[-3].token.value
            return_type: str = extract_type(func_firm.nodes[-4])
            params_node: ast.ASTRef = func_firm.nodes[-2]

            if method_name in ('self', 'cls'):
                raise RuntimeError(f"No se puede usar el identificador reservado '{method_name}' como nombre de método en la clase '{class_name}'.")
            if method_name in local_methods:
                raise RuntimeError(f"Método duplicado '{method_name}' en la clase '{class_name}'.")
            local_methods.add(method_name)




            # Determinar tipo de método
            if dec_name == 'classmethod' or method_name == '__new__':
                kind = 'classmethod'
            elif dec_name == 'staticmethod':
                kind = 'staticmethod'
            else:
                kind = 'instance'

            # Validar retorno de métodos mágicos intrínsecos
            if method_name in ('__init__', '__new__') and return_type != 'void':
                raise TypeError(
                    f"El método mágico '{method_name}' de la clase '{class_name}' debe retornar 'void', pero se declaró como '{return_type}'."
                )

            if method_name == '__init__' and class_obj.bases:
                # Si la subclase define su propio __init__, la unión de campos de instancia
                # de las clases base se realiza al invocar 'super().__init__()'.
                class_obj.instance_fields.clear()


            method_obj = ClassMethod(
                name=method_name,
                return_type=return_type,
                kind=kind, # type: ignore
                decorator=dec_name,
                class_decl=class_obj,
                privacy=privacy, # type: ignore
                in_scope=storage,
            )

            # LocalStorage para el método
            local_storage = LocalStorage(function=method_obj, parent=storage)
            method_obj.scope = local_storage

            # Configuración de punteros contextuales implícitos
            if kind == 'instance':
                self_var = Variable(name='self', value=None, type=f"{class_name}*", is_constant=True, privacy='private')
                local_storage.variables['self'] = self_var
            elif kind == 'classmethod':
                cls_var = Variable(name='cls', value=None, type=f"{class_name}_Class*", is_constant=True, privacy='private')
                local_storage.variables['cls'] = cls_var
                if method_name == '__new__':
                    # Soportar self como alias de cls dentro de __new__
                    local_storage.variables['self'] = cls_var

            # Validar que staticmethod no contenga self ni cls
            if kind == 'staticmethod':
                _validate_staticmethod_no_self_cls(params_node, method_name)
                _validate_staticmethod_no_self_cls(func_body, method_name)

            # Extraer parámetros (sin requerir self ni cls)
            process_parameters(local_storage, method_obj, params_node)

            # Procesar sentencias del cuerpo
            _process_method_body(local_storage, method_obj, class_obj, func_body, inherited_from)

            # Registrar método
            class_obj.methods[method_name] = method_obj
            if kind == 'instance':
                class_obj.instance_methods[method_name] = method_obj
            elif kind == 'classmethod':
                class_obj.class_methods[method_name] = method_obj
            elif kind == 'staticmethod':
                class_obj.static_methods[method_name] = method_obj

            if method_name == '__init__':
                class_obj.init_method = method_obj
            elif method_name == '__new__':
                class_obj.new_method = method_obj

    # 7. Autogeneración de __new__ y __init__ si están ausentes
    if class_obj.new_method is None:
        auto_new = ClassMethod(
            name='__new__',
            return_type='void',
            kind='classmethod',
            class_decl=class_obj,
            in_scope=storage,
        )
        auto_new.scope = LocalStorage(function=auto_new, parent=storage)
        class_obj.new_method = auto_new
        class_obj.methods['__new__'] = auto_new
        class_obj.class_methods['__new__'] = auto_new

    if class_obj.init_method is None:
        auto_init = ClassMethod(
            name='__init__',
            return_type='void',
            kind='instance',
            class_decl=class_obj,
            in_scope=storage,
        )
        auto_init.scope = LocalStorage(function=auto_init, parent=storage)
        class_obj.init_method = auto_init
        class_obj.methods['__init__'] = auto_init
        class_obj.instance_methods['__init__'] = auto_init

    return class_obj




__all__ = [
    'visit_class',
]

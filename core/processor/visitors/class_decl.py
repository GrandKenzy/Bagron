import gram
from core.processor.objects.class_decl import ClassDecl, ClassMethod
from core.processor.objects.function import Function, FunctionParam
from core.processor.visitors.func_decl import _parse_param, parse_body_statements
from core.processor.type_system import register_type, CUSTOM_TYPES

def visit(node: gram.ASTNode) -> ClassDecl:
    vals = [str(v.value if hasattr(v, 'value') else v) for v in node.values]
    privacity = 'public'
    if 'private' in vals:
        privacity = 'private'
    name = vals[-1]

    register_type(name, name, field_name='self')
    if name in CUSTOM_TYPES:
        CUSTOM_TYPES[name]['is_class'] = True
    if name.startswith('inmodule_'):
        parts = name.split('_', 2)
        if len(parts) >= 3:
            mod_part = parts[1]
            short_name = parts[-1]
            register_type(short_name, name, field_name='self')
            if short_name in CUSTOM_TYPES:
                CUSTOM_TYPES[short_name]['is_class'] = True
            register_type(f'{mod_part}.{short_name}', name, field_name='self')
            if f'{mod_part}.{short_name}' in CUSTOM_TYPES:
                CUSTOM_TYPES[f'{mod_part}.{short_name}']['is_class'] = True

    fields = []
    field_map = {}

    body_nodes = node.find('EGL_CLASS_BODY')
    body_children = body_nodes[0].children if body_nodes else []

    for child in body_children:
        if child.name in ('EGL_VAR_DECL', 'var declaration'):
            spec = child.find('EGL_TYPE_SPEC')
            f_type = spec[0].values[0] if spec and spec[0].values else None

            mem_acc = child.find('EGL_MEMBER_ACCESS')
            if mem_acc:
                mem_vals = [str(getattr(v, 'value', v)) for v in mem_acc[0].values]
                if len(mem_vals) >= 2 and mem_vals[0] in ('self', 'this'):
                    f_name = mem_vals[1]
                    if f_type is None:
                        raise TypeError(f"El campo 'self.{f_name}' de la clase '{name}' debe tener un tipo explícito.")
                    field_map[f_name] = str(f_type)
                    continue

            f_name_raw = child.values[-1] if child.values else ''
            f_name_str = str(getattr(f_name_raw, 'value', f_name_raw))
            if f_name_str and not f_name_str.startswith(('self.', 'this.')):
                if f_type is None:
                    raise TypeError(f"El campo '{f_name_str}' de la clase '{name}' debe tener un tipo explícito.")
                field_map[f_name_str] = str(f_type)

        elif child.name in ('EGL_ASSIGN', 'assign'):
            mem_acc = child.find('EGL_MEMBER_ACCESS')
            if mem_acc:
                mem_vals = [str(getattr(v, 'value', v)) for v in mem_acc[0].values]
                if len(mem_vals) >= 2 and mem_vals[0] in ('self', 'this'):
                    f_name = mem_vals[1]
                    if f_name not in field_map:
                        inferred = None
                        call_nodes = child.find('EGL_CALL')
                        if call_nodes:
                            call_name = str(call_nodes[0].values[0] if call_nodes[0].values else '')
                            from core.externs.manager import manager
                            ext_sym = manager.find_backend_symbol(call_name)
                            if ext_sym:
                                inferred = ext_sym[0].get('return_type')
                            elif hasattr(node, 'parent') and node.parent:
                                for fn in node.parent.find('EGL_FUNC_DECL'):
                                    fn_spec = fn.find('EGL_TYPE_SPEC')
                                    fn_name = fn.values[-1] if fn.values else ''
                                    if str(fn_name) == call_name and fn_spec:
                                        inferred = str(fn_spec[0].values[0])
                                        break
                        if not inferred:
                            raise TypeError(f"El campo 'self.{f_name}' de la clase '{name}' debe tener un tipo explícito.")
                        field_map[f_name] = inferred

    methods = {}
    generated_functions = []
    method_nodes = [c for c in body_children if c.name in ('EGL_METHOD_DECL', 'method declaration')]
    if not method_nodes:
        method_nodes = node.find('EGL_METHOD_DECL')
    init_func = None

    is_packed = False
    packed_nodes = node.find('EGL_PACKED')
    if packed_nodes or any(getattr(c, 'name', '') in ('EGL_PACKED', '__packed__') for c in body_children):
        is_packed = True
        is_struct = 'struct' in vals
        if not is_struct:
            raise SyntaxError(f"El modificador '__packed__' solo está permitido en 'struct', no en 'class' ('{name}').")
        if method_nodes:
            raise SyntaxError(f"El struct empaquetado '__packed__' ('{name}') debe ser un struct simple (solo campos de datos, sin métodos).")

    for m in method_nodes:
        spec_nodes = m.find('EGL_TYPE_SPEC')
        ret_type = str(spec_nodes[0].values[0]) if spec_nodes and spec_nodes[0].values else 'void'
        m_name = str(m.values[-1]) if m.values else '__init__'

        is_magic = m_name.startswith('__') and m_name.endswith('__')
        dec_nodes = m.find('EGL_DECORATOR')
        has_method_dec = any(str(getattr(v, 'value', v)) == 'method' for d in dec_nodes for v in d.values)

        if not is_magic and not has_method_dec:
            raise SyntaxError(f"El método '{m_name}' de la clase '{name}' debe llevar el decorador '@method'.")

        params = []
        user_params = []
        for p in m.find('EGL_PARAM'):
            parsed_p = _parse_param(p)
            if parsed_p.name in ('self', 'this'):
                raise SyntaxError(f"El parámetro '{parsed_p.name}' es implícito en los métodos de la clase '{name}' y no debe declararse en la firma.")
            params.append(parsed_p)
            user_params.append(parsed_p)

        all_params = [FunctionParam(f'{name}*', 'self')] + params

        body_subnodes = m.find('EGL_FUNC_BODY')
        method_body = {}
        returned = None
        if body_subnodes:
            parsed_b, parsed_ret, _ = parse_body_statements(body_subnodes[0].children)
            method_body.update(parsed_b)
            returned = parsed_ret

        full_fn_name = f'{name}_{m_name}'
        fn_obj = Function(full_fn_name, method_body, ret_type, all_params, privacity=privacity).rescope()
        fn_obj.returned = returned
        fn_obj.parent_class = name
        methods[m_name] = fn_obj
        generated_functions.append(fn_obj)

        if m_name in ('__init__', 'init') and init_func is None:
            init_func = (m_name, user_params)
            for v_decl in m.find('EGL_VAR_DECL'):
                mem_acc = v_decl.find('EGL_MEMBER_ACCESS')
                if mem_acc:
                    mem_vals = [str(getattr(v, 'value', v)) for v in mem_acc[0].values]
                    if len(mem_vals) >= 2 and mem_vals[0] in ('self', 'this'):
                        f_name = mem_vals[1]
                        spec = v_decl.find('EGL_TYPE_SPEC')
                        f_type = spec[0].values[0] if spec and spec[0].values else None
                        if f_name not in field_map:
                            field_map[f_name] = str(f_type or 'void*')
            for ass in m.find('EGL_ASSIGN'):
                mem_acc = ass.find('EGL_MEMBER_ACCESS')
                if mem_acc:
                    mem_vals = [str(getattr(v, 'value', v)) for v in mem_acc[0].values]
                    if len(mem_vals) >= 2 and mem_vals[0] in ('self', 'this'):
                        f_name = mem_vals[1]
                        if f_name not in field_map:
                            inferred = None
                            val_nodes = ass.find('EGL_VALUE')
                            if val_nodes and val_nodes[0].values:
                                val_p = str(val_nodes[0].values[0])
                                for up_type, up_name in user_params:
                                    if up_name == val_p:
                                        inferred = up_type
                                        break
                            if not inferred:
                                call_nodes = ass.find('EGL_CALL')
                                if call_nodes:
                                    call_name = str(call_nodes[0].values[0] if call_nodes[0].values else '')
                                    from core.externs.manager import manager
                                    ext_sym = manager.find_backend_symbol(call_name)
                                    if ext_sym:
                                        inferred = ext_sym[0].get('return_type')
                            if not inferred:
                                raise TypeError(f"El campo 'self.{f_name}' de la clase '{name}' debe tener un tipo explícito.")
                            field_map[f_name] = inferred

    for f_name, f_type in field_map.items():
        fields.append({'name': f_name, 'type': f_type})

    if init_func:
        ctor_params = init_func[1]
        ctor_call_args = [p[1] for p in ctor_params]
        init_m_name = init_func[0]
        args_str = (', ' + ', '.join(ctor_call_args)) if ctor_call_args else ''
        init_call = f'{name}_{init_m_name}(&self{args_str});'
    elif fields:
        ctor_params = [FunctionParam(f['type'], f['name'], has_default=True, default=0) for f in fields]
        field_assignments = '\n'.join([f'    self.{f["name"]} = {f["name"]};' for f in fields])
        init_call = field_assignments
    else:
        ctor_params = []
        init_call = ''

    ctor_fn_name = f'{name}_create'
    ctor_fn = Function(ctor_fn_name, {}, name, ctor_params, privacity='public')
    ctor_fn.init_call = init_call
    ctor_fn.is_constructor = True
    generated_functions.append(ctor_fn)

    class_obj = ClassDecl(
        name=name,
        methods=methods,
        fields=fields,
        privacity=privacity,
        is_packed=is_packed
    )
    class_obj.constructor_func = ctor_fn
    class_obj.generated_functions = generated_functions
    if name in CUSTOM_TYPES:
        CUSTOM_TYPES[name]['methods'] = set(methods.keys())
        CUSTOM_TYPES[name]['class_decl'] = class_obj
    return class_obj

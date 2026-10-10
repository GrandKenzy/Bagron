import gram
from core.processor.objects.class_decl import ClassDecl, ClassMethod
from core.processor.objects.function import Function
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

    fields = []
    field_map = {}

    for v_decl in node.find('EGL_VAR_DECL'):
        spec = v_decl.find('EGL_TYPE_SPEC')
        f_type = spec[0].values[0] if spec and spec[0].values else None

        mem_acc = v_decl.find('EGL_MEMBER_ACCESS')
        if mem_acc:
            mem_vals = [str(getattr(v, 'value', v)) for v in mem_acc[0].values]
            if len(mem_vals) >= 2 and mem_vals[0] in ('self', 'this'):
                f_name = mem_vals[1]
                if f_type is None:
                    raise TypeError(f"El campo 'self.{f_name}' de la clase '{name}' debe tener un tipo explícito.")
                field_map[f_name] = str(f_type)
                continue

        toks = [str(getattr(t, 'value', t)) for t in getattr(v_decl, 'all_tokens', [])]
        f_name_raw = v_decl.values[-1] if v_decl.values else (toks[-1] if toks else '')
        f_name_str = str(getattr(f_name_raw, 'value', f_name_raw))
        if f_name_str and not f_name_str.startswith(('self.', 'this.')):
            if f_type is None:
                raise TypeError(f"El campo '{f_name_str}' de la clase '{name}' debe tener un tipo explícito.")
            field_map[f_name_str] = str(f_type)

    for ass in node.find('EGL_ASSIGN'):
        toks = [str(getattr(t, 'value', t)) for t in getattr(ass, 'all_tokens', [])]
        if len(toks) >= 3 and toks[0] in ('self', 'this') and toks[1] == '.':
            f_name = toks[2]
            if f_name not in field_map:
                inferred = None
                call_nodes = ass.find('EGL_CALL')
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

    for f_name, f_type in field_map.items():
        fields.append({'name': f_name, 'type': f_type})

    methods = {}
    generated_functions = []
    method_nodes = node.find('EGL_METHOD_DECL')
    init_func = None

    for m in method_nodes:
        spec_nodes = m.find('EGL_TYPE_SPEC')
        ret_type = str(spec_nodes[0].values[0]) if spec_nodes and spec_nodes[0].values else 'void'
        m_name = str(m.values[-1]) if m.values else '__init__'

        is_magic = m_name.startswith('__') and m_name.endswith('__')
        all_tok_values = [str(getattr(t, 'value', t)) for t in getattr(m, 'all_tokens', [])]
        has_method_dec = False
        for i, tok_val in enumerate(all_tok_values):
            if tok_val == '@' and i + 1 < len(all_tok_values) and all_tok_values[i + 1] == 'method':
                has_method_dec = True
                break
            if tok_val == '@method':
                has_method_dec = True
                break

        if not is_magic and not has_method_dec:
            raise SyntaxError(f"El método '{m_name}' de la clase '{name}' debe llevar el decorador '@method'.")

        params = []
        user_params = []
        for p in m.find('EGL_PARAM'):
            v_str = str(p.values[0] if p.values else '')
            tok_strs = [str(getattr(t, 'value', t)) for t in getattr(p, 'all_tokens', [])]
            if v_str in ('self', 'this') or (tok_strs and tok_strs[0] in ('self', 'this')):
                continue
            parsed_p = _parse_param(p)
            params.append(parsed_p)
            user_params.append(parsed_p)

        all_params = [(f'{name}*', 'self')] + params

        body_subnodes = m.find('EGL_FUNC_BODY')
        method_body = {}
        returned = None
        if body_subnodes:
            parsed_b, parsed_ret, _ = parse_body_statements(body_subnodes[0].children)
            method_body.update(parsed_b)
            returned = parsed_ret

        full_fn_name = f'{name}_{m_name}'
        fn_obj = Function(full_fn_name, method_body, ret_type, all_params, privacity=privacity)
        fn_obj.returned = returned
        methods[m_name] = fn_obj
        generated_functions.append(fn_obj)

        if m_name in ('__init__', 'init') and init_func is None:
            init_func = (m_name, user_params)

    from core.processor.objects.function import FunctionParam
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

    from core.backend.c.visitors.variable import convert_type
    c_param_decls = [f'{convert_type(p[0])} {p[1]}' for p in ctor_params]
    ctor_sig = f'{name} {ctor_fn_name}({", ".join(c_param_decls)})'
    ctor_code = f'{ctor_sig} {{\n    {name} self;\n    memset(&self, 0, sizeof({name}));\n'
    if init_call:
        ctor_code += f'    {init_call}\n'
    ctor_code += '    return self;\n}'
    ctor_fn.compiled = ctor_code
    generated_functions.append(ctor_fn)

    class_obj = ClassDecl(
        name=name,
        methods=methods,
        fields=fields,
        privacity=privacity
    )
    class_obj.constructor_func = ctor_fn
    class_obj.generated_functions = generated_functions
    return class_obj

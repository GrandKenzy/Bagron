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
    body_nodes = node.find('EGL_CLASS_BODY')
    body_children = body_nodes[0].children if body_nodes else []

    for c in body_children:
        if c.name in ('EGL_VAR_DECL', 'var declaration'):
            toks = [str(getattr(t, 'value', t)) for t in getattr(c, 'all_tokens', [])]
            spec = c.find('EGL_TYPE_SPEC')
            f_type = spec[0].values[0] if spec and spec[0].values else (toks[0] if toks else 'any')
            f_name = c.values[-1] if c.values else (toks[-1] if toks else '')
            fields.append({'name': str(f_name), 'type': str(f_type)})

    for ass in (body_nodes[0].find('EGL_ASSIGN') if body_nodes else []):
        toks = [str(getattr(t, 'value', t)) for t in getattr(ass, 'all_tokens', [])]
        if len(toks) >= 3 and toks[0] == 'self' and toks[1] == '.':
            f_name = toks[2]
            if not any(f['name'] == f_name for f in fields):
                fields.append({'name': f_name, 'type': 'ptr' if 'handle' in f_name.lower() or 'ptr' in f_name.lower() else 'any'})

    methods = {}
    generated_functions = []
    method_nodes = node.find('EGL_METHOD_DECL')
    init_func = None

    for m in method_nodes:
        spec_nodes = m.find('EGL_TYPE_SPEC')
        ret_type = str(spec_nodes[0].values[0]) if spec_nodes and spec_nodes[0].values else 'void'
        m_name = str(m.values[-1]) if m.values else '__init__'

        params = []
        user_params = []
        for p in m.find('EGL_PARAM'):
            v_str = str(p.values[0] if p.values else '')
            tok_strs = [str(getattr(t, 'value', t)) for t in getattr(p, 'all_tokens', [])]
            if v_str in ('self', 'this') or (tok_strs and tok_strs[0] in ('self', 'this')):
                continue
            parsed_p = _parse_param(p)
            params.append((parsed_p.type, parsed_p.name))
            user_params.append((parsed_p.type, parsed_p.name))

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

    ctor_params = init_func[1] if init_func else []
    ctor_call_args = [p[1] for p in ctor_params]
    ctor_fn_name = f'{name}_create'
    ctor_fn = Function(ctor_fn_name, {}, name, ctor_params, privacity='public')

    if init_func:
        init_m_name = init_func[0]
        args_str = (', ' + ', '.join(ctor_call_args)) if ctor_call_args else ''
        init_call = f'{name}_{init_m_name}(&self{args_str});'
    else:
        init_call = ''

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

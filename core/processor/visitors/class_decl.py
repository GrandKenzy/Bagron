import gram
from core.processor.objects.class_decl import ClassDecl, ClassMethod
from core.processor.type_system import register_type

def visit(node: gram.ASTNode) -> ClassDecl:
    vals = [str(v.value if hasattr(v, 'value') else v) for v in node.values]
    privacity = 'public'
    if 'private' in vals:
        privacity = 'private'
    name = vals[-1]
    
    methods = {}
    fields = []

    method_nodes = node.find('EGL_METHOD_DECL')
    for m in method_nodes:
        m_vals = [str(v.value if hasattr(v, 'value') else v) for v in m.values]
        decorator = None
        if len(m_vals) >= 2 and m_vals[0] == 'method':
            decorator = 'method'
            m_name = m_vals[1]
        elif m_vals:
            m_name = m_vals[-1]
        else:
            m_name = ''

        ret_nodes = m.find('EGL_TYPE_SPEC')
        ret_type = 'void'
        if ret_nodes and ret_nodes[0].values:
            ret_type = str(ret_nodes[0].values[0])

        params = []
        for p in m.find('EGL_PARAM'):
            p_vals = [str(v.value if hasattr(v, 'value') else v) for v in p.values]
            params.append(p_vals)

        body_nodes = m.find('EGL_FUNC_BODY')
        body_node = body_nodes[0] if body_nodes else None

        method_obj = ClassMethod(
            name=m_name,
            return_type=ret_type,
            params=params,
            decorator=decorator,
            body_node=body_node,
            privacity='public'
        )
        methods[m_name] = method_obj

    fields_dict = {}
    for m in method_nodes:
        m_vals = [str(v.value if hasattr(v, 'value') else v) for v in m.values]
        if not any(v in ('__new__', '__init__') for v in m_vals):
            continue
        for vd in m.find('EGL_VAR_DECL'):
            mems = vd.find('EGL_MEMBER_ACCESS')
            if mems and mems[0].values:
                mv = [str(x.value if hasattr(x, 'value') else x) for x in mems[0].values]
                if len(mv) >= 2 and mv[0] == 'self':
                    f_name = mv[1]
                    f_spec = vd.find('EGL_TYPE_SPEC')
                    f_type = 'any'
                    if f_spec and f_spec[0].values:
                        sv = [str(x.value if hasattr(x, 'value') else x) for x in f_spec[0].values]
                        f_type = ' '.join(sv)
                    fields_dict[f_name] = {'name': f_name, 'type': f_type}
        for ass in m.find('EGL_ASSIGN'):
            mems = ass.find('EGL_MEMBER_ACCESS')
            if mems and mems[0].values:
                mv = [str(x.value if hasattr(x, 'value') else x) for x in mems[0].values]
                if len(mv) >= 2 and mv[0] == 'self':
                    f_name = mv[1]
                    if f_name not in fields_dict:
                        fields_dict[f_name] = {'name': f_name, 'type': 'auto'}

    fields = list(fields_dict.values())
    for c in node.children:
        if c.name in ('EGL_VAR_DECL', 'var declaration'):
            fields.append(c)

    register_type(name, 'class', field_name='self')

    class_obj = ClassDecl(
        name=name,
        methods=methods,
        fields=fields,
        privacity=privacity
    )
    return class_obj

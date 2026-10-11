import gram
from core.initiator import reserve_funnames
from core.processor.objects import *
from core.processor.visitors.call import extract_call_args

def _find_call(node: gram.ASTNode) -> gram.ASTNode | None:
    for sub in node.walk():
        if sub.name in ('EGL_CALL', 'call', 'EGL_METHOD_CALL', 'method call'):
            return sub
    return None

def visit(node: gram.ASTNode):
    vals = list(node.values)
    privacity = 'public'
    if vals and vals[0] in ('public', 'private'):
        privacity = vals.pop(0)

    spec_nodes = node.find('EGL_TYPE_SPEC')
    t = 'any'
    element_type = None
    fixed_size = None
    type_args = []
    is_pointer_type = False

    if spec_nodes and spec_nodes[0].values:
        spec_vals = [str(v.value if hasattr(v, 'value') else v) for v in spec_nodes[0].values]
        spec_toks = [str(tok.value) for tok in getattr(spec_nodes[0], 'tokens', []) if str(tok.value) != '*']
        if '.' in spec_toks:
            t = ''.join(spec_toks)
        else:
            t = spec_vals[0]
        if '*' in spec_vals:
            is_pointer_type = True
        if len(spec_vals) > 1:
            for extra in spec_vals[1:]:
                if extra == '*':
                    continue
                if extra.isdigit():
                    fixed_size = int(extra)
                    type_args.append(int(extra))
                else:
                    element_type = extra
                    type_args.append(extra)
        from core.processor.type_system import resolve_generic_type
        gen_elem, gen_size = resolve_generic_type(t, type_args)
        if gen_elem is not None:
            element_type = gen_elem
        if gen_size is not None:
            fixed_size = gen_size
    elif vals:
        t = str(vals.pop(0))
        if vals and isinstance(vals[0], (int, float)):
            fixed_size = int(vals.pop(0))

    val_nodes = node.find('EGL_VALUE')
    lhs_mem_nodes = [n for n in node.find('EGL_MEMBER_ACCESS') if not val_nodes or n not in val_nodes[0].walk()]
    if lhs_mem_nodes and lhs_mem_nodes[0].values:
        m_vals = [str(getattr(v, 'value', v)) for v in lhs_mem_nodes[0].values]
        name = '.'.join(m_vals)
    else:
        ident_tokens = [tok for tok in getattr(node, 'tokens', []) if getattr(getattr(tok, 'token', None), 'name', '') == 'IDENT' or str(getattr(tok, 'token', '')) == 'Token.IDENT']
        if ident_tokens:
            name = str(getattr(ident_tokens[0], 'value', ident_tokens[0]))
        else:
            name = str(getattr(vals[0], 'value', vals[0])) if vals else ''
    
    call_node = _find_call(node)
    pointer_base_type = None
    is_call_ptr = False

    if call_node and call_node.name in ('EGL_METHOD_CALL', 'method call'):
        from core.externs.manager import manager
        raw_target = call_node.values[0]
        target = str(getattr(raw_target, 'value', raw_target))
        if len(call_node.values) >= 3 and str(getattr(call_node.values[1], 'value', call_node.values[1])) == '.':
            raw_m = call_node.values[2]
        elif len(call_node.values) >= 2:
            raw_m = call_node.values[1]
        else:
            raw_m = ''
        method = str(getattr(raw_m, 'value', raw_m))
        args, _ = extract_call_args(call_node)
        if manager.has_namespace(target):
            sym = manager.validate_call(target, method, args)
            ret_type = sym.get('return_type', 'void')
            if ret_type == 'ptr' or sym.get('is_pointer'):
                is_call_ptr = True
        value = MethodCall(target, method, args).ignore()
    elif call_node:
        raw_c = call_node.values[0]
        call_name = str(getattr(raw_c, 'value', raw_c))
        args, kwargs = extract_call_args(call_node)
        value = Call(call_name, args, kwargs).ignore()
        reserved = reserve_funnames.get_items().get(call_name)
        if reserved and reserved.returntype == 'ptr':
            is_call_ptr = True
        elif not reserved:
            from core.externs.manager import manager
            ext_sym = manager.find_backend_symbol(call_name)
            if ext_sym and (ext_sym[0].get('return_type') == 'ptr' or ext_sym[0].get('is_pointer')):
                is_call_ptr = True
        if call_name == 'malloc':
            raw_base = kwargs.get('Type') if 'Type' in kwargs else (args[0] if len(args) >= 2 else None)
            if raw_base:
                pointer_base_type = str(getattr(raw_base, 'value', raw_base))
    else:
        val_nodes = node.find('EGL_VALUE')
        if val_nodes:
            from core.processor.visitors import expression as expr_visitor
            value = expr_visitor.visit(val_nodes[0])
        elif node.children and len(node.children) > 1:
            from core.processor.visitors import expression as expr_visitor
            value = expr_visitor.visit(node.children[-1])
        elif len(vals) >= 2:
            value = vals[1]
        else:
            value = None

    is_constant = name.strip('_').isupper()

    v = Variable(name, value, t, privacity, is_constant)
    if fixed_size is not None:
        v.fixed_size = fixed_size
    if element_type is not None:
        v.element_type = element_type
    if type_args:
        v.type_args = type_args
    if t in ('ptr', '__void_p_t__', 'pointer') or is_call_ptr or is_pointer_type:
        v.is_pointer = True
        if pointer_base_type:
            v.pointer_base_type = pointer_base_type
        elif element_type:
            v.pointer_base_type = element_type

    if isinstance(value, gram.Identifier):
        v.ref = True
    return v
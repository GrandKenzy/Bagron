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

    mem_nodes = node.find('EGL_MEMBER_ACCESS')
    if mem_nodes and mem_nodes[0].values:
        m_vals = [str(v.value if hasattr(v, 'value') else v) for v in mem_nodes[0].values]
        name = '.'.join(m_vals)
    else:
        name = str(vals[0].value if hasattr(vals[0], 'value') else vals[0]) if vals else ''
    
    call_node = _find_call(node)
    pointer_base_type = None
    is_call_ptr = False

    if call_node and call_node.name in ('EGL_METHOD_CALL', 'method call'):
        from core.externs.manager import manager
        target = str(call_node.values[0].value if hasattr(call_node.values[0], 'value') else call_node.values[0])
        method = str(call_node.values[2].value if len(call_node.values) >= 3 else (call_node.values[1].value if hasattr(call_node.values[1], 'value') else call_node.values[1]))
        args, _ = extract_call_args(call_node)
        if manager.has_namespace(target):
            sym = manager.validate_call(target, method, args)
            ret_type = sym.get('return_type', 'void')
            if ret_type == 'ptr' or sym.get('is_pointer'):
                is_call_ptr = True
        value = MethodCall(target, method, args).ignore()
    elif call_node:
        call_name = str(call_node.values[0].value if hasattr(call_node.values[0], 'value') else call_node.values[0])
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
                pointer_base_type = str(raw_base.value if hasattr(raw_base, 'value') else raw_base)
    elif len(vals) >= 2:
        value = vals[1]
    else:
        val_nodes = node.find('EGL_VALUE')
        if val_nodes and val_nodes[0].values:
            idx_nodes = val_nodes[0].find('EGL_INDEX_ACCESS')
            if idx_nodes:
                idx = idx_nodes[0]
                target_idx = str(idx.values[0])
                idx_child = idx.children[0] if idx.children else None
                idx_expr = ''.join(str(getattr(t, 'value', t)) for t in getattr(idx_child, 'all_tokens', idx_child.values)) if idx_child else ''
                value = f'{target_idx}[{idx_expr}]'
            else:
                all_t = getattr(val_nodes[0], 'all_tokens', [])
                if len(all_t) > 1 or val_nodes[0].find('EGL_MEMBER_ACCESS'):
                    value = ''.join(str(getattr(t, 'value', t)) for t in all_t)
                elif len(val_nodes[0].values) == 1:
                    value = val_nodes[0].values[0]
                else:
                    value = ''.join(str(getattr(t, 'value', t)) for t in all_t)
        elif node.children and len(node.children) > 1:
            value = node.children[-1].values if node.children[-1].values else None
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
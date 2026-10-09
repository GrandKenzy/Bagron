import gram
from core.initiator import reserve_funnames
from core.processor.objects import *
from core.processor.visitors.call import extract_call_args

def _find_call(node: gram.ASTNode) -> gram.ASTNode | None:
    for sub in node.walk():
        if sub.name in ('EGL_CALL', 'call'):
            return sub
    return None

def visit(node: gram.ASTNode):
    vals = list(node.values)
    privacity = 'public'
    if vals and vals[0] in ('public', 'private'):
        privacity = vals.pop(0)
    t = str(vals.pop(0))
    fixed_size = None
    if vals and isinstance(vals[0], (int, float)):
        fixed_size = int(vals.pop(0))
    name = str(vals[0].value if hasattr(vals[0], 'value') else vals[0]) if vals else ''
    
    call_node = _find_call(node)
    pointer_base_type = None
    is_call_ptr = False

    if call_node:
        call_name = str(call_node.values[0].value if hasattr(call_node.values[0], 'value') else call_node.values[0])
        args, kwargs = extract_call_args(call_node)
        value = Call(call_name, args, kwargs).ignore()
        reserved = reserve_funnames.get_items().get(call_name)
        if reserved and reserved.returntype == 'ptr':
            is_call_ptr = True
        if call_name == 'malloc' and (args or kwargs):
            raw_base = kwargs.get('Type') if 'Type' in kwargs else (args[0] if args else None)
            if raw_base:
                pointer_base_type = str(raw_base.value if hasattr(raw_base, 'value') else raw_base)
    elif len(vals) >= 2:
        value = vals[1]
    elif node.children:
        value = node.children[0].value
    else:
        value = None

    is_constant = name.strip('_').isupper()

    v = Variable(name, value, t, privacity, is_constant)
    v.fixed_size = fixed_size
    if t == 'ptr' or is_call_ptr:
        v.is_pointer = True
        if pointer_base_type:
            v.pointer_base_type = pointer_base_type

    if isinstance(value, gram.Identifier):
        v.ref = True
    return v
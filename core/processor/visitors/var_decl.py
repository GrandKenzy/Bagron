import gram
from core.processor.objects import *  

def visit(node: gram.ASTNode):
    t, name, value = node.values
    
    name: str = name
    privacity = 'public' if not name.startswith('_') else 'private'
    is_constant = name.strip('_').isupper()

    v = Variable(name, value, t, privacity, is_constant)
    
    if isinstance(value, gram.Identifier):
        v.ref = True
    return v
    
    
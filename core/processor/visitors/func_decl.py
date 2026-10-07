import gram
from core.processor.objects import *
from core.processor.visitors import var_decl


def visit(node: gram.ASTNode):
    return_type, name = node.values
    params = []
    body =  {}
    returned: Returned | None = None 
    
    
    for child in node.children:
        if child.name == 'ec_params':
            for param in child.children:
                param_type, param_name = param.values
                params.append((param_type, param_name))
        elif child.name == 'func body':
            for statement in child.children:
                if statement.name == 'var declaration':
                    v = var_decl.visit(statement).ignore()
                    body[v] = 'Variable'
                elif statement.name == 'return':
                    returned = Returned(statement.values[1]).ignore()
                else:
                    print('falta por procesar', statement.name)
    func = Function(name, body, return_type, params, privacity='public').rescope()
    func.returned = returned
    return func
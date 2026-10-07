import gram
from core.processor.visitors import *
from core.processor import objects


def process(ast: gram.ASTProgram):
    
    for node in ast.walk(0):
        if node.name == 'var declaration':
            var_decl.visit(node)
        elif node.name == 'func declaration':
            func_decl.visit(node)
        else:
            print('Falta por procedsar o node: ', node.name)
        
    return  objects.get_items()
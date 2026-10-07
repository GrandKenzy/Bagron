import gram
from core.processor.visitors import *
from core.processor import objects


def process(ast: gram.ASTProgram):
    
    for node in ast.walk():
        if node.name == 'var declaration':
            var_decl.visit(node)
        else:
            print('Falta por procedsar o node: ', node.name)
        
    return  objects.get_items()
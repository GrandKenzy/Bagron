import gram

def visit_decl(node: gram.ASTNode):
    t, name, value = node.values
    
    # acá hacer cualquier lógica de backend
    
    # luego vamos a transformar a C
    
    if t == 'char':
        value = f"'{value}'"
    
    code = f"{t} {name} = {value}"; print(code); return code 
    
    

def process(ast: gram.ASTProgram):
    
    
    for node in ast.blocks():
        # hay que sacar el nodo de la lista de valores del DECLARADOR
        child = node.children[0] 
        
        if child.name == 'var declaration':
            visit_decl(child)
        
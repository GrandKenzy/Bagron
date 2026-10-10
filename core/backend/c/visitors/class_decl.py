from typing import Callable
from core.processor.objects.class_decl import ClassDecl
from core.backend.c.visitors.variable import convert_type
import core.backend.c as c_backend

def visit(class_obj: ClassDecl, processor: Callable):
    c_backend.add_include('<string.h>')
    c_backend.add_include('<stdlib.h>')

    fields_code = []
    for f in class_obj.fields:
        f_name = f['name']
        f_type = convert_type(f['type'])
        if f_type in ('', 'any', 'auto'):
            f_type = 'void*' if 'handle' in f_name.lower() or 'ptr' in f_name.lower() else 'int'
        fields_code.append(f'    {f_type} {f_name};')

    if not fields_code:
        fields_code.append('    int __dummy;')

    fields_body = '\n'.join(fields_code)
    typedef_def = f'typedef struct {class_obj.name} {{\n{fields_body}\n}} {class_obj.name};'
    c_backend.add_typedef(typedef_def)

    for method_func in getattr(class_obj, 'generated_functions', []):
        if method_func == getattr(class_obj, 'constructor_func', None):
            continue
        from core.backend.c.visitors import function as fn_visitor
        fn_visitor.visit(method_func, processor)

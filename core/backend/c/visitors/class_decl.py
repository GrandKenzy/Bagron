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
        if not f_type or f_type in ('any', 'auto'):
            f_type = 'void*'
        fields_code.append(f'    {f_type} {f_name};')

    if not fields_code:
        fields_code.append('    int __dummy;')

    fields_body = '\n'.join(fields_code)
    if getattr(class_obj, 'is_packed', False):
        typedef_def = (
            f'#ifdef _MSC_VER\n'
            f'#pragma pack(push, 1)\n'
            f'typedef struct {class_obj.name} {{\n'
            f'{fields_body}\n'
            f'}} {class_obj.name};\n'
            f'#pragma pack(pop)\n'
            f'#else\n'
            f'typedef struct __attribute__((__packed__)) {class_obj.name} {{\n'
            f'{fields_body}\n'
            f'}} {class_obj.name};\n'
            f'#endif'
        )
    else:
        typedef_def = f'typedef struct {class_obj.name} {{\n{fields_body}\n}} {class_obj.name};'
    c_backend.add_typedef(typedef_def)

    ctor = getattr(class_obj, 'constructor_func', None)
    if ctor and not getattr(ctor, 'compiled', None):
        c_param_decls = [f'{convert_type(p[0])} {p[1]}' for p in getattr(ctor, 'parameters', [])]
        ctor_sig = f'{class_obj.name} {ctor.name}({", ".join(c_param_decls)})'
        init_call = getattr(ctor, 'init_call', '')
        ctor_code = f'{ctor_sig} {{\n    {class_obj.name} self;\n    memset(&self, 0, sizeof({class_obj.name}));\n'
        if init_call:
            ctor_code += f'    {init_call}\n'
        ctor_code += '    return self;\n}'
        ctor.compiled = ctor_code

    for method_func in getattr(class_obj, 'generated_functions', []):
        if method_func == ctor:
            continue
        from core.backend.c.visitors import function as fn_visitor
        fn_visitor.visit(method_func, processor)

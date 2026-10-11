from core.processor.objects import *
from core.backend.c.visitors import *
from core.backend.c.detectors import detect_includes
from core.backend.c.deffunc import deffunc
from core.backend.c.compile import compile, SUPPORTED_COMPILERS, DEFAULT_COMPILER, CLI_COMPILER_PARAMS
from core.backend.c.download import download_compiler, download_gcc, download_msvc

includes: list[str] = []
typedefs: list[str] = []

def add_include(header: str):
    if not header.startswith('#include'):
        if not (header.startswith('<') or header.startswith('"')):
            header = f'<{header}>'
        header = f'#include {header}'
    if header not in includes:
        includes.append(header)

def clear():
    includes.clear()
    typedefs.clear()

def add_typedef(definition: str):
    if definition not in typedefs:
        typedefs.append(definition)

def process(content: dict[Object, str], block: Function | None = None):
    items = list(content.items())
    type_items = [it for it in items if isinstance(it[0], (ClassDecl, EnumDecl, TypeDecl))]
    other_items = [it for it in items if not isinstance(it[0], (ClassDecl, EnumDecl, TypeDecl))]
    ordered_items = type_items + other_items

    for item, _ in ordered_items:
        for inc in detect_includes(item):
            add_include(inc)
        if isinstance(item, ClassDecl):
            class_decl.visit(item, process)
        elif isinstance(item, EnumDecl):
            enum_decl.visit(item)
        elif isinstance(item, Variable):
            variable.visit(item, block)
        elif isinstance(item, Function):
            function.visit(item, process)
        elif isinstance(item, IfStatement):
            if_statement.visit(item, block)
        elif isinstance(item, ForStatement):
            for_statement.visit(item, block)
        elif isinstance(item, WhileStatement):
            while_statement.visit(item, block)
        elif isinstance(item, Assign):
            assign.visit(item, block)
        elif isinstance(item, Call):
            compiled_call = deffunc(item.name, item.args, getattr(item, 'kwargs', {}), is_statement=True, block=block)
            item.compiled = compiled_call.compiled
        elif isinstance(item, MethodCall):
            method_call.visit(item, is_statement=True, block=block)

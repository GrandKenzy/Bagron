from core.processor.objects import *
from core.backend.c.visitors import *
from core.backend.c.detectors import detect_includes
from core.backend.c.deffunc import deffunc

includes: list[str] = []

def add_include(header: str):
    if not header.startswith('#include'):
        if not (header.startswith('<') or header.startswith('"')):
            header = f'<{header}>'
        header = f'#include {header}'
    if header not in includes:
        includes.append(header)

def process(content: dict[Object, str], block: Function | None = None):
    if block is None:
        includes.clear()
    for item, _ in list(content.items()):
        for inc in detect_includes(item):
            add_include(inc)
        if isinstance(item, Variable):
            variable.visit(item, block)
        elif isinstance(item, Function):
            function.visit(item, process)
        elif isinstance(item, IfStatement):
            if_statement.visit(item, block)
        elif isinstance(item, ForStatement):
            for_statement.visit(item, block)
        elif isinstance(item, Assign):
            assign.visit(item, block)
        elif isinstance(item, Call):
            compiled_call = deffunc(item.name, item.args, getattr(item, 'kwargs', {}), is_statement=True, block=block)
            item.compiled = compiled_call.compiled

from core.processor.objects import *
from core.backend.c.visitors import *

def process(content: dict[Object, str], block: Function | None = None):
    for item, _ in content.items():
        if isinstance(item, Variable):
            variable.visit(item, block)
        elif isinstance(item, Function):
            function.visit(item, process)



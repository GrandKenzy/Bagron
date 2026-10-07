from core.processor.objects import base
from core.processor.objects.base import Object
from core.processor.objects.variable import Variable
from core.processor.objects.function import Function
from core.processor.objects.returned import Returned

def get_items():
    return base.ITEMS

def get_vars():
    return [item for item in get_items() if isinstance(item, Variable)]

__all__ = [
    'Variable',
    'Function',
    'Object',
    'Returned',
    
    'get_items',
    'get_vars',
]
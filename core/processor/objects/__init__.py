from core.processor.objects import base
from core.processor.objects.variable import Variable
from core.processor.objects.function import Function

def get_items():
    return base.ITEMS

__all__ = [
    'Variable',
    'Function',
]
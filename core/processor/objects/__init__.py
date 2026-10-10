from core.processor.objects import base
from core.processor.objects.base import Object
from core.processor.objects.variable import Variable
from core.processor.objects.function import Function, FunctionParam
from core.processor.objects.returned import Returned
from core.processor.objects.call import Call
from core.processor.objects.assign import Assign
from core.processor.objects.if_statement import IfStatement
from core.processor.objects.for_statement import ForStatement
from core.processor.objects.while_statement import WhileStatement
from core.processor.objects.method_call import MethodCall
from core.processor.objects.member_access import MemberAccess
from core.processor.objects.type_decl import TypeDecl
from core.processor.objects.enum_decl import EnumDecl
from core.processor.objects.class_decl import ClassDecl, ClassMethod

def get_items():
    return base.ITEMS

def get_vars():
    return [item for item in get_items() if isinstance(item, Variable)]

def clear():
    base.ITEMS.clear()

__all__ = [
    'Variable',
    'Function',
    'FunctionParam',
    'Object',
    'Returned',
    'Call',
    'Assign',
    'IfStatement',
    'ForStatement',
    'WhileStatement',
    'MethodCall',
    'MemberAccess',
    'TypeDecl',
    'EnumDecl',
    'ClassDecl',
    'ClassMethod',
    'get_items',
    'get_vars',
]
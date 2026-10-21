from core.processor.objects import base
from core.processor.objects.array import Array
from core.processor.objects.base import Object
from core.processor.objects.variable import Variable
from core.processor.objects.function import Function, FunctionParam, LocalStorage

from core.processor.objects.returned import Returned
from core.processor.objects.call import Call
from core.processor.objects.assign import Assign
from core.processor.objects.if_statement import ElifClause, IfStatement
from core.processor.objects.for_statement import ForStatement
from core.processor.objects.while_statement import WhileStatement
from core.processor.objects.method_call import MethodCall, SuperInitCall
from core.processor.objects.member_access import MemberAccess
from core.processor.objects.type_decl import TypeAlias, TypeDecl
from core.processor.objects.enum_decl import EnumDecl
from core.processor.objects.struct_decl import StructDecl, StructField
from core.processor.objects.class_decl import ClassDecl, ClassMethod, ClassField
from core.processor.objects.expression import BinaryExpr, UnaryExpr, LiteralExpr, VariableExpr, IndexAccess

def get_items():
    return base.ITEMS

def get_vars():
    return [item for item in get_items() if isinstance(item, Variable)]

def clear():
    base.ITEMS.clear()

__all__ = [
    'Array',
    'Variable',
    'Function',

    'FunctionParam',
    'LocalStorage',
    'Object',
    'Returned',
    'Call',
    'Assign',
    'ElifClause',
    'IfStatement',
    'ForStatement',
    'WhileStatement',
    'MethodCall',
    'SuperInitCall',
    'MemberAccess',
    'TypeAlias',
    'TypeDecl',
    'EnumDecl',
    'StructDecl',
    'StructField',
    'ClassDecl',
    'ClassMethod',
    'ClassField',
    'BinaryExpr',
    'UnaryExpr',
    'LiteralExpr',
    'VariableExpr',
    'IndexAccess',
    'get_items',
    'get_vars',
    'clear',
]
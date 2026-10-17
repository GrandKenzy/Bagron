"""Catálogo exhaustivo de métodos mágicos de Easy-C con sus valores por defecto.

Este módulo define la especificación canónica de todos los métodos mágicos (dunder methods),
su vinculación a operadores/protocolos y sus valores por defecto cuando no son declarados
explícitamente en una clase (siempre retornan 'void' o '0').
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class MagicMethodInfo:
    """Especificación técnica de un método mágico en Easy-C."""
    name: str
    operator: str | None
    category: str
    default_return_type: Literal['void', 'int']
    default_return_value: Literal['void', '0']
    min_args: int
    max_args: int
    param_names: tuple[str, ...]
    description: str


# ==============================================================================
# CATÁLOGO DE MÉTODOS MÁGICOS
# ==============================================================================
MAGIC_METHODS: dict[str, MagicMethodInfo] = {
    # --------------------------------------------------------------------------
    # 1. Ciclo de Vida e Instanciación (Lifecycle)
    # --------------------------------------------------------------------------
    '__new__': MagicMethodInfo(
        name='__new__',
        operator=None,
        category='lifecycle',
        default_return_type='void',
        default_return_value='void',
        min_args=0,
        max_args=255,
        param_names=('cls',),
        description='Constructor y asignador de memoria de bajo nivel. En Easy-C retorna void.',
    ),
    '__init__': MagicMethodInfo(
        name='__init__',
        operator=None,
        category='lifecycle',
        default_return_type='void',
        default_return_value='void',
        min_args=0,
        max_args=255,
        param_names=('self',),
        description='Inicializador de campos de instancia. En Easy-C retorna void.',
    ),
    '__del__': MagicMethodInfo(
        name='__del__',
        operator=None,
        category='lifecycle',
        default_return_type='void',
        default_return_value='void',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Destructor / liberador de recursos (RAII). Invocado al destruir la instancia.',
    ),

    # --------------------------------------------------------------------------
    # 2. Operadores Unarios (Unary)
    # --------------------------------------------------------------------------
    '__pos__': MagicMethodInfo(
        name='__pos__',
        operator='+',
        category='unary',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Operador unario positivo (+self). Si no se declara, retorna 0.',
    ),
    '__neg__': MagicMethodInfo(
        name='__neg__',
        operator='-',
        category='unary',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Operador unario de negación aritmética (-self). Si no se declara, retorna 0.',
    ),
    '__invert__': MagicMethodInfo(
        name='__invert__',
        operator='~',
        category='unary',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Operador de complemento a uno a nivel de bits (~self). Si no se declara, retorna 0.',
    ),
    '__abs__': MagicMethodInfo(
        name='__abs__',
        operator='abs',
        category='unary',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Función o cálculo de valor absoluto intrínseco (abs(self)). Si no se declara, retorna 0.',
    ),

    # --------------------------------------------------------------------------
    # 3. Operadores Aritméticos Binarios (Arithmetic)
    # --------------------------------------------------------------------------
    '__add__': MagicMethodInfo(
        name='__add__',
        operator='+',
        category='arithmetic',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Suma binaria (self + other). Si no se declara, retorna 0.',
    ),
    '__sub__': MagicMethodInfo(
        name='__sub__',
        operator='-',
        category='arithmetic',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Resta binaria (self - other). Si no se declara, retorna 0.',
    ),
    '__mul__': MagicMethodInfo(
        name='__mul__',
        operator='*',
        category='arithmetic',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Multiplicación (self * other). Si no se declara, retorna 0.',
    ),
    '__truediv__': MagicMethodInfo(
        name='__truediv__',
        operator='/',
        category='arithmetic',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='División real o estándar (self / other). Si no se declara, retorna 0.',
    ),
    '__floordiv__': MagicMethodInfo(
        name='__floordiv__',
        operator='//',
        category='arithmetic',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='División entera de piso (self // other). Si no se declara, retorna 0.',
    ),
    '__mod__': MagicMethodInfo(
        name='__mod__',
        operator='%',
        category='arithmetic',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Resto de división entera o módulo (self % other). Si no se declara, retorna 0.',
    ),
    '__pow__': MagicMethodInfo(
        name='__pow__',
        operator='**',
        category='arithmetic',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Exponenciación (self ** other). Si no se declara, retorna 0.',
    ),

    # --------------------------------------------------------------------------
    # 4. Operadores a Nivel de Bits (Bitwise)
    # --------------------------------------------------------------------------
    '__lshift__': MagicMethodInfo(
        name='__lshift__',
        operator='<<',
        category='bitwise',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Desplazamiento a la izquierda (self << other). Si no se declara, retorna 0.',
    ),
    '__rshift__': MagicMethodInfo(
        name='__rshift__',
        operator='>>',
        category='bitwise',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Desplazamiento a la derecha (self >> other). Si no se declara, retorna 0.',
    ),
    '__and__': MagicMethodInfo(
        name='__and__',
        operator='&',
        category='bitwise',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Operador AND a nivel de bits (self & other). Si no se declara, retorna 0.',
    ),
    '__xor__': MagicMethodInfo(
        name='__xor__',
        operator='^',
        category='bitwise',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Operador XOR a nivel de bits (self ^ other). Si no se declara, retorna 0.',
    ),
    '__or__': MagicMethodInfo(
        name='__or__',
        operator='|',
        category='bitwise',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Operador OR a nivel de bits (self | other). Si no se declara, retorna 0.',
    ),

    # --------------------------------------------------------------------------
    # 5. Operadores Compuestos de Asignación en Sitio (In-place)
    # --------------------------------------------------------------------------
    '__iadd__': MagicMethodInfo(
        name='__iadd__',
        operator='+=',
        category='inplace',
        default_return_type='void',
        default_return_value='void',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Asignación compuesta suma (self += other). Si no se declara, retorna void.',
    ),
    '__isub__': MagicMethodInfo(
        name='__isub__',
        operator='-=',
        category='inplace',
        default_return_type='void',
        default_return_value='void',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Asignación compuesta resta (self -= other). Si no se declara, retorna void.',
    ),
    '__imul__': MagicMethodInfo(
        name='__imul__',
        operator='*=',
        category='inplace',
        default_return_type='void',
        default_return_value='void',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Asignación compuesta multiplicación (self *= other). Si no se declara, retorna void.',
    ),
    '__itruediv__': MagicMethodInfo(
        name='__itruediv__',
        operator='/=',
        category='inplace',
        default_return_type='void',
        default_return_value='void',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Asignación compuesta división (self /= other). Si no se declara, retorna void.',
    ),
    '__ifloordiv__': MagicMethodInfo(
        name='__ifloordiv__',
        operator='//=',
        category='inplace',
        default_return_type='void',
        default_return_value='void',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Asignación compuesta división entera (self //= other). Si no se declara, retorna void.',
    ),
    '__imod__': MagicMethodInfo(
        name='__imod__',
        operator='%=',
        category='inplace',
        default_return_type='void',
        default_return_value='void',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Asignación compuesta módulo (self %= other). Si no se declara, retorna void.',
    ),
    '__ipow__': MagicMethodInfo(
        name='__ipow__',
        operator='**=',
        category='inplace',
        default_return_type='void',
        default_return_value='void',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Asignación compuesta potencia (self **= other). Si no se declara, retorna void.',
    ),
    '__ilshift__': MagicMethodInfo(
        name='__ilshift__',
        operator='<<=',
        category='inplace',
        default_return_type='void',
        default_return_value='void',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Asignación compuesta desplazamiento izquierda (self <<= other). Si no se declara, retorna void.',
    ),
    '__irshift__': MagicMethodInfo(
        name='__irshift__',
        operator='>>=',
        category='inplace',
        default_return_type='void',
        default_return_value='void',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Asignación compuesta desplazamiento derecha (self >>= other). Si no se declara, retorna void.',
    ),
    '__iand__': MagicMethodInfo(
        name='__iand__',
        operator='&=',
        category='inplace',
        default_return_type='void',
        default_return_value='void',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Asignación compuesta AND a nivel de bits (self &= other). Si no se declara, retorna void.',
    ),
    '__ixor__': MagicMethodInfo(
        name='__ixor__',
        operator='^=',
        category='inplace',
        default_return_type='void',
        default_return_value='void',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Asignación compuesta XOR a nivel de bits (self ^= other). Si no se declara, retorna void.',
    ),
    '__ior__': MagicMethodInfo(
        name='__ior__',
        operator='|=',
        category='inplace',
        default_return_type='void',
        default_return_value='void',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Asignación compuesta OR a nivel de bits (self |= other). Si no se declara, retorna void.',
    ),

    # --------------------------------------------------------------------------
    # 6. Operadores de Comparación Relacional (Comparison)
    # --------------------------------------------------------------------------
    '__eq__': MagicMethodInfo(
        name='__eq__',
        operator='==',
        category='comparison',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Igualdad (self == other). Si no se declara, retorna 0 (falso).',
    ),
    '__ne__': MagicMethodInfo(
        name='__ne__',
        operator='!=',
        category='comparison',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Desigualdad (self != other). Si no se declara, retorna 0.',
    ),
    '__lt__': MagicMethodInfo(
        name='__lt__',
        operator='<',
        category='comparison',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Menor estricto (self < other). Si no se declara, retorna 0.',
    ),
    '__le__': MagicMethodInfo(
        name='__le__',
        operator='<=',
        category='comparison',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Menor o igual (self <= other). Si no se declara, retorna 0.',
    ),
    '__gt__': MagicMethodInfo(
        name='__gt__',
        operator='>',
        category='comparison',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Mayor estricto (self > other). Si no se declara, retorna 0.',
    ),
    '__ge__': MagicMethodInfo(
        name='__ge__',
        operator='>=',
        category='comparison',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'other'),
        description='Mayor o igual (self >= other). Si no se declara, retorna 0.',
    ),

    # --------------------------------------------------------------------------
    # 7. Evaluación Booleana / Lógica (Logical)
    # --------------------------------------------------------------------------
    '__bool__': MagicMethodInfo(
        name='__bool__',
        operator='bool',
        category='logical',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Evaluación booleana o de verdad. Si no se declara, retorna 0 (falso).',
    ),

    # --------------------------------------------------------------------------
    # 8. Colecciones, Índices y Secuencias (Container)
    # --------------------------------------------------------------------------
    '__len__': MagicMethodInfo(
        name='__len__',
        operator='len',
        category='container',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Longitud de contenedor o arreglo (len(self)). Si no se declara, retorna 0.',
    ),
    '__getitem__': MagicMethodInfo(
        name='__getitem__',
        operator='[]',
        category='container',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'key'),
        description='Acceso a índice o clave de lectura (self[key]). Si no se declara, retorna 0.',
    ),
    '__setitem__': MagicMethodInfo(
        name='__setitem__',
        operator='[]=',
        category='container',
        default_return_type='void',
        default_return_value='void',
        min_args=2,
        max_args=2,
        param_names=('self', 'key', 'value'),
        description='Asignación por índice o clave (self[key] = value). Si no se declara, retorna void.',
    ),
    '__delitem__': MagicMethodInfo(
        name='__delitem__',
        operator='del []',
        category='container',
        default_return_type='void',
        default_return_value='void',
        min_args=1,
        max_args=1,
        param_names=('self', 'key'),
        description='Eliminación de elemento por índice o clave (del self[key]). Si no se declara, retorna void.',
    ),
    '__contains__': MagicMethodInfo(
        name='__contains__',
        operator='in',
        category='container',
        default_return_type='int',
        default_return_value='0',
        min_args=1,
        max_args=1,
        param_names=('self', 'item'),
        description='Pertenencia a contenedor (item in self). Si no se declara, retorna 0.',
    ),

    # --------------------------------------------------------------------------
    # 9. Protocolo de Iteración (Iteration)
    # --------------------------------------------------------------------------
    '__iter__': MagicMethodInfo(
        name='__iter__',
        operator='iter',
        category='iteration',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Inicialización de iterador. Si no se declara, retorna 0 (puntero nulo).',
    ),
    '__next__': MagicMethodInfo(
        name='__next__',
        operator='next',
        category='iteration',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Siguiente elemento de la iteración. Si no se declara, retorna 0.',
    ),

    # --------------------------------------------------------------------------
    # 10. Objetos Invocables (Callable)
    # --------------------------------------------------------------------------
    '__call__': MagicMethodInfo(
        name='__call__',
        operator='()',
        category='callable',
        default_return_type='void',
        default_return_value='void',
        min_args=0,
        max_args=255,
        param_names=('self',),
        description='Invocación directa de la instancia como función (self(...)). Si no se declara, retorna void.',
    ),

    # --------------------------------------------------------------------------
    # 11. Conversiones y Representación (Conversion)
    # --------------------------------------------------------------------------
    '__str__': MagicMethodInfo(
        name='__str__',
        operator='str',
        category='conversion',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Representación legible en cadena de texto. Si no se declara, retorna 0 (puntero nulo).',
    ),
    '__repr__': MagicMethodInfo(
        name='__repr__',
        operator='repr',
        category='conversion',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Representación canónica o para depuración. Si no se declara, retorna 0.',
    ),
    '__hash__': MagicMethodInfo(
        name='__hash__',
        operator='hash',
        category='conversion',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Cálculo del código hash entero (hash(self)). Si no se declara, retorna 0.',
    ),
    '__int__': MagicMethodInfo(
        name='__int__',
        operator='int',
        category='conversion',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Conversión explícita a entero nativo (int(self)). Si no se declara, retorna 0.',
    ),
    '__float__': MagicMethodInfo(
        name='__float__',
        operator='float',
        category='conversion',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Conversión explícita a punto flotante (float(self)). Si no se declara, retorna 0.',
    ),

    # --------------------------------------------------------------------------
    # 12. Gestores de Contexto (Context)
    # --------------------------------------------------------------------------
    '__enter__': MagicMethodInfo(
        name='__enter__',
        operator='with',
        category='context',
        default_return_type='void',
        default_return_value='void',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Entrada al bloque de contexto (with self:). Si no se declara, retorna void.',
    ),
    '__exit__': MagicMethodInfo(
        name='__exit__',
        operator='with',
        category='context',
        default_return_type='void',
        default_return_value='void',
        min_args=3,
        max_args=3,
        param_names=('self', 'exc_type', 'exc_val', 'exc_tb'),
        description='Salida del bloque de contexto. Si no se declara, retorna void.',
    ),

    # --------------------------------------------------------------------------
    # 13. Gestión de Memoria y Tamaño (Memory)
    # --------------------------------------------------------------------------
    '__sizeof__': MagicMethodInfo(
        name='__sizeof__',
        operator='sizeof',
        category='memory',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Tamaño en bytes ocupado en memoria (sizeof(self)). Si no se declara, retorna 0.',
    ),
    '__copy__': MagicMethodInfo(
        name='__copy__',
        operator='copy',
        category='memory',
        default_return_type='int',
        default_return_value='0',
        min_args=0,
        max_args=0,
        param_names=('self',),
        description='Copia superficial de la instancia. Si no se declara, retorna 0.',
    ),
}


# ==============================================================================
# MAPEO INVERSO DE OPERADORES A MÉTODOS MÁGICOS
# ==============================================================================
OPERATOR_TO_MAGIC: dict[str, str] = {
    '+': '__add__',
    '-': '__sub__',
    '*': '__mul__',
    '/': '__truediv__',
    '//': '__floordiv__',
    '%': '__mod__',
    '**': '__pow__',
    '<<': '__lshift__',
    '>>': '__rshift__',
    '&': '__and__',
    '^': '__xor__',
    '|': '__or__',
    '+=': '__iadd__',
    '-=': '__isub__',
    '*=': '__imul__',
    '/=': '__itruediv__',
    '//=': '__ifloordiv__',
    '%=': '__imod__',
    '**=': '__ipow__',
    '<<=': '__ilshift__',
    '>>=': '__irshift__',
    '&=': '__iand__',
    '^=': '__ixor__',
    '|=': '__ior__',
    '==': '__eq__',
    '!=': '__ne__',
    '<': '__lt__',
    '<=': '__le__',
    '>': '__gt__',
    '>=': '__ge__',
    '[]': '__getitem__',
    '[]=': '__setitem__',
    'del []': '__delitem__',
    'in': '__contains__',
    '~': '__invert__',
}


# ==============================================================================
# FUNCIONES DE CONSULTA Y VALIDACIÓN
# ==============================================================================
def is_magic_method(name: str) -> bool:
    """Verifica si un nombre corresponde a un método mágico canónico de Easy-C."""
    return name in MAGIC_METHODS


def get_magic_method(name: str) -> MagicMethodInfo | None:
    """Retorna la especificación técnica del método mágico o None si no existe."""
    return MAGIC_METHODS.get(name)


def get_default_return(name: str) -> tuple[str, str]:
    """Retorna el par (tipo_retorno, valor_retorno) por defecto para el método mágico cuando no se declara.
    
    Garantía de diseño de Easy-C: siempre retorna 'void' o '0'.
    """
    spec = MAGIC_METHODS.get(name)
    if spec is not None:
        return (spec.default_return_type, spec.default_return_value)
    # Por defecto para cualquier método dunder no registrado
    return ('void', 'void') if name.endswith(('setitem__', 'init__', 'del__')) else ('int', '0')


def get_operator_magic(op: str) -> MagicMethodInfo | None:
    """Retorna la especificación del método mágico asociado a un operador o None si no aplica."""
    method_name = OPERATOR_TO_MAGIC.get(op)
    if method_name:
        return MAGIC_METHODS.get(method_name)
    return None


def get_magic_methods_by_category(category: str) -> list[MagicMethodInfo]:
    """Retorna todos los métodos mágicos pertenecientes a una categoría dada."""
    return [m for m in MAGIC_METHODS.values() if m.category == category]


def get_void_defaults() -> list[str]:
    """Retorna la lista de métodos mágicos cuyo valor de retorno por defecto es 'void'."""
    return [name for name, spec in MAGIC_METHODS.items() if spec.default_return_type == 'void']


def get_zero_defaults() -> list[str]:
    """Retorna la lista de métodos mágicos cuyo valor de retorno por defecto es '0'."""
    return [name for name, spec in MAGIC_METHODS.items() if spec.default_return_value == '0']


__all__ = [
    'MagicMethodInfo',
    'MAGIC_METHODS',
    'OPERATOR_TO_MAGIC',
    'is_magic_method',
    'get_magic_method',
    'get_default_return',
    'get_operator_magic',
    'get_magic_methods_by_category',
    'get_void_defaults',
    'get_zero_defaults',
]

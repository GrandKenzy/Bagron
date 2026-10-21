from collections.abc import Callable
from typing import Any


class ReservedFunc:
    def __init__(
        self,
        name: str,
        processor: Callable[[Any], Any] | None = None,
        returned: str = 'void',
        c_header: str | None = None,
        c_equivalent: str | None = None,
        is_variadic: bool = False,
        description: str = '',
        **params: Any,
    ):
        self.name = name
        self.processor = processor
        self.returned = returned
        self.c_header = c_header
        self.c_equivalent = c_equivalent
        self.is_variadic = is_variadic
        self.description = description
        self.params = params
        MagicFuncsManager.add(self)

    def __repr__(self) -> str:
        return f"<ReservedFunc {self.name} -> {self.returned}>"


class MagicFuncsManager:
    _reserves: dict[str, ReservedFunc] = {}

    @classmethod
    def add(cls, func: ReservedFunc) -> None:
        if func.name in cls._reserves:
            raise RuntimeError(f"No se puede reemplazar la función intrínseca reservada '{func.name}'.")
        cls._reserves[func.name] = func

    @classmethod
    def exists(cls, name: str) -> bool:
        return name in cls._reserves

    @classmethod
    def get(cls, name: str) -> ReservedFunc | None:
        return cls._reserves.get(name)

    @classmethod
    def run(cls, name: str, node: Any) -> Any:
        func = cls.get(name)
        if func and func.processor:
            return func.processor(node)
        return None

    @classmethod
    def all(cls) -> dict[str, ReservedFunc]:
        return cls._reserves

    @classmethod
    def get_items(cls) -> dict[str, ReservedFunc]:
        """Backward-compatible alias for legacy callers."""
        return cls._reserves


# Backward-compatible module-level helper
def exists(name: str) -> bool:
    return MagicFuncsManager.exists(name)


def get_items() -> dict[str, ReservedFunc]:
    return MagicFuncsManager.get_items()


# ==============================================================================
# PROCESSORS (Stubs listos para implementar en la fase de procesamiento de tokens)
# ==============================================================================

def visit_print(node: Any) -> Any:
    # Transforma argumentos dinámicos a printf() con sus formatos según el tipo en C
    pass


def visit_input(node: Any) -> Any:
    # Emite fgets() o lectura segura de buffer en C
    pass


def visit_sizeof(node: Any) -> Any:
    # Emite sizeof(T) nativo de C
    pass


def visit_free(node: Any) -> Any:
    # Emite free(ptr) de <stdlib.h> en C
    pass


def visit_version(node: Any) -> Any:
    # Emite constante literal "1.0.0" en tiempo de compilación
    pass


# ==============================================================================
# DECLARACIÓN DE INTRÍNSECOS
# ==============================================================================

r_print = ReservedFunc(
    'print',
    visit_print,
    returned='void',
    c_header='stdio.h',
    c_equivalent='printf',
    is_variadic=True,
    description='Imprime valores formateados por consola con salto de línea',
    VALUES={'type': ['ptr', 'char', 'chain', 'any'], 'expand': True},
    sep={'type': ['ptr', 'char', 'chain', 'any'], 'default': ' '},
)

r_input = ReservedFunc(
    'input',
    visit_input,
    returned='chain',
    c_header='stdio.h',
    c_equivalent='_ec_input',
    is_variadic=False,
    description='Lee una línea de texto de la entrada estándar',
    prompt={'type': ['chain', 'char', 'ptr', 'any'], 'default': ''},
)

r_sizeof = ReservedFunc(
    'sizeof',
    visit_sizeof,
    returned='wsize',
    c_header='stddef.h',
    c_equivalent='sizeof',
    is_variadic=False,
    description='Obtiene el tamaño en bytes de un tipo o variable',
    target={'type': 'any'},
)

r_free = ReservedFunc(
    'free',
    visit_free,
    returned='void',
    c_header='stdlib.h',
    c_equivalent='free',
    is_variadic=False,
    description='Libera un bloque de memoria asignado dinámicamente',
    ptr={'type': 'ptr'},
)

r_version = ReservedFunc(
    'EGL_Version',
    visit_version,
    returned='chain',
    c_header=None,
    c_equivalent='"1.0.0"',
    is_variadic=False,
    description='Obtiene la versión del compilador Easy-C',
)



__all__ = [
    'MagicFuncsManager',
    'ReservedFunc',
    'exists',
    'get_items',
    'r_free',
    'r_input',
    'r_print',
    'r_sizeof',
    'r_version',
]

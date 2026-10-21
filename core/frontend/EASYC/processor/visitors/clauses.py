import platform

from gram import ast

from core.processor.storage import Storage

optimizations: list[str] = ['debug', 'production', 'modern']
privacy: list[str] = ['private', 'public']
targets: list[str] = ['auto', 'gcc', 'msvc', 'clang']
architectures: list[str] = ['amd', 'arm', 'x86']
systems: list[str] = ['windows', 'linux', 'macos']


# Detección automática basada en el sistema operativo actual
_sys_raw = platform.system().lower()
if 'win' in _sys_raw:
    SYSTEM = 'windows'
elif 'dar' in _sys_raw or 'mac' in _sys_raw:
    SYSTEM = 'macos'
else:
    SYSTEM = 'linux'

_mach_raw = platform.machine().lower()
if 'arm' in _mach_raw or 'aarch' in _mach_raw:
    ARCH = 'arm'
elif '64' in _mach_raw or 'amd' in _mach_raw:
    ARCH = 'amd'
else:
    ARCH = 'x86'

TARGET: str = 'gcc' if SYSTEM in ['linux', 'macos'] else 'msvc'


def visit_clause(storage: Storage, node: ast.ASTRef):
    target = str(node.nodes[1].token.value)  # type: ignore
    raw = node.nodes[2].token.value  # type: ignore
    val = str(raw).strip('"\'').lower()

    if target == 'Arch':
        if val not in architectures:
            raise ValueError(f"Arquitectura no válida: {val!r}. Opciones permitidas: {architectures}")
        storage.arch = val
    elif target == 'System':
        if val not in systems:
            raise ValueError(f"Sistema no válido: {val!r}. Opciones permitidas: {systems}")
        storage.system = val
    elif target == 'Visibility':
        if val not in privacy:
            raise ValueError(f"Visibilidad no válida: {val!r}. Opciones permitidas: {privacy}")
        storage.privacy = val
    elif target == 'StackLimit':
        storage.stacklimit = int(raw)
    elif target == 'CompilerTarget': 
        if val not in targets:
            raise ValueError(f"CompilerTarget no válido: {val!r}. Opciones permitidas: {targets}")
        storage.compiler_target = val
    elif target == 'Optimizations':
        if val not in optimizations:
            raise ValueError(f"Optimización no válida: {val!r}. Opciones permitidas: {optimizations}")
        storage.optimizations = val


__all__ = [
    'visit_clause',
]
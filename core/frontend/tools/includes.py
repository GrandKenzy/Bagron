from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

from gram import ast as gast

from core.frontend.objects import NativeInclude

if TYPE_CHECKING:
    from core.compiler import Compiler


def _children(node: object) -> list[object]:
    if isinstance(node, list):
        return list(node)
    nodes = getattr(node, 'nodes', None)
    if nodes is not None:
        return list(nodes)
    items = getattr(node, 'items', None)
    if items is not None:
        return list(items)
    return []


def _token_kind(node: object) -> str | None:
    token = getattr(node, 'token', None)
    token = getattr(token, 'token', token)
    return getattr(token, 'name', None)


def _token_value(node: object) -> object | None:
    token = getattr(node, 'token', None)
    return getattr(token, 'value', None)


def _string_values(node: object) -> list[str]:
    values: list[str] = []
    if _token_kind(node) == 'STRING':
        value = _token_value(node)
        if value is not None:
            values.append(str(value))
    for child in _children(node):
        values.extend(_string_values(child))
    return values


def _normalize_header(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError('El nombre del header no puede estar vacio')
    if name.lower().endswith('.h'):
        return name
    return f'{name}.h'


def _normalize_library(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError('El nombre de la libreria no puede estar vacio')
    for suffix in ('.lib', '.dll', '.a', '.so'):
        if name.lower().endswith(suffix):
            name = name[:-len(suffix)]
            break
    if name.lower().startswith('lib'):
        name = name[3:]
    if not name:
        raise ValueError('El nombre de la libreria no puede estar vacio')
    return name


def _header_is_available(compiler: Compiler, header: str) -> bool:
    from core.backend.llvm.targets import resolve_target

    clang = shutil.which('clang')
    if clang is None:
        compiler.error(
            'No se encontro clang para resolver headers nativos: '
            f'{header}'
        )
        return False

    try:
        target = resolve_target(compiler.storage.architecture).triple
    except (TypeError, ValueError, RuntimeError) as error:
        compiler.error(f'No se pudo resolver el target para {header}: {error}')
        return False

    command = [
        clang,
        f'--target={target}',
        '-E',
        '-x',
        'c',
        '-include',
        header,
        '-',
    ]
    try:
        result = subprocess.run(
            command,
            input='',
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        compiler.error(f'No se pudo resolver el header {header}: {error}')
        return False

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        compiler.error(
            f'No se encontro el header nativo {header}: {detail}'
        )
        return False
    return True


def validate(compiler: Compiler, node: gast.ASTRef) -> NativeInclude | None:
    values = _string_values(node)
    if len(values) != 2:
        compiler.error(
            'La declaracion include requiere un header y una libreria: '
            'include "header" link "library"'
        )
        return None

    try:
        header = _normalize_header(values[0])
        library = _normalize_library(values[1])
    except ValueError as error:
        compiler.error(str(error))
        return None

    if not _header_is_available(compiler, header):
        return None

    include = NativeInclude(header=header, library=library)
    if include not in compiler.storage.native_includes:
        compiler.storage.native_includes.append(include)
    if library not in compiler.storage.native_links:
        compiler.storage.native_links.append(library)
    return include


__all__ = ['validate']

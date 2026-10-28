from __future__ import annotations

from typing import TYPE_CHECKING

from gram import ast as gast

from core.frontend.objects import FunctionSignature, FunctionSymbol, TypeSpec
from core.frontend.tools.function import _parameter_items, _parameter_spec
from core.frontend.tools.types import (
    INTEGER_TYPES,
    TypeResolutionError,
    resolve_type,
)

if TYPE_CHECKING:
    from core.compiler import Compiler


_UNSUPPORTED_ABI_TYPES = {'chain', 'callptr', 'Null'}


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


def _identifier(node: object) -> str | None:
    if _token_kind(node) == 'IDENT':
        return str(_token_value(node))
    for child in _children(node):
        found = _identifier(child)
        if found is not None:
            return found
    return None


def _string_value(node: object) -> str | None:
    if _token_kind(node) == 'STRING':
        value = _token_value(node)
        return str(value) if value is not None else None
    for child in _children(node):
        found = _string_value(child)
        if found is not None:
            return found
    return None


def _extern_body(node: gast.ASTRef) -> gast.ASTRef | None:
    return next(
        (
            child for child in _children(node)
            if isinstance(child, gast.ASTRef) and child.name == 'EXTERN_BODY'
        ),
        None,
    )


def _extern_functions(body: gast.ASTRef) -> list[gast.ASTRef]:
    result: list[gast.ASTRef] = []
    for child in _children(body):
        if isinstance(child, gast.ASTRef) and child.name == 'EXTERN_FUNCTION':
            result.append(child)
            continue
        result.extend(
            item for item in _children(child)
            if isinstance(item, gast.ASTRef) and item.name == 'EXTERN_FUNCTION'
        )
    return result


def _return_spec(node: gast.ASTRef) -> TypeSpec:
    return_node = next(
        (
            child for child in _children(node)
            if isinstance(child, gast.ASTRef) and child.name == 'EXTERN_RETURN'
        ),
        None,
    )
    if return_node is None:
        raise TypeResolutionError('La declaracion extern no tiene retorno')

    def pointer_count(current: object) -> int:
        if isinstance(current, gast.ASTRef) and current.name == 'POINTER':
            return len(current.nodes)
        return sum(pointer_count(child) for child in _children(current))

    pointer_level = pointer_count(return_node)
    type_node = None
    for child in reversed(_children(return_node)):
        if _token_kind(child) == 'COLON':
            continue
        if pointer_count(child):
            continue
        type_node = child
        break

    if type_node is None:
        raise TypeResolutionError('La declaracion extern no tiene un tipo de retorno')
    return resolve_type(type_node, pointer_level=pointer_level)


def _validate_abi_type(
    compiler: Compiler,
    type_spec: TypeSpec,
    context: str,
    *,
    is_return: bool = False,
) -> None:
    if type_spec.array_depth:
        raise TypeResolutionError(
            f'{context} no puede usar arrays en una firma extern'
        )
    if type_spec.name in _UNSUPPORTED_ABI_TYPES:
        raise TypeResolutionError(
            f'{context} usa un tipo no disponible en la ABI: '
            f'{type_spec.canonical_name}'
        )
    if type_spec.name == 'void' and not type_spec.pointer_level and not is_return:
        raise TypeResolutionError(f'{context} no puede usar void por valor')
    scalar_names = INTEGER_TYPES | {'bool', 'char'}
    pointer_base_names = scalar_names | {'float', 'double', 'middle', 'void'}
    if type_spec.pointer_level:
        if type_spec.name in pointer_base_names:
            return
        if compiler.storage.resolve_type(type_spec.name) is not None:
            return
        raise TypeResolutionError(
            f'{context} usa un tipo desconocido: {type_spec.canonical_name}'
        )
    if type_spec.name in scalar_names:
        return
    if type_spec.name == 'void' and is_return:
        return
    raise TypeResolutionError(
        f'{context} usa un escalar no soportado por la ABI actual: '
        f'{type_spec.canonical_name}'
    )


def _normalize_library(name: str) -> str:
    name = name.strip()
    if not name:
        raise TypeResolutionError('El nombre de la libreria extern esta vacio')
    for suffix in ('.lib', '.dll', '.a', '.so'):
        if name.lower().endswith(suffix):
            name = name[:-len(suffix)]
            break
    if name.lower().startswith('lib'):
        name = name[3:]
    if not name:
        raise TypeResolutionError('El nombre de la libreria extern esta vacio')
    return name


def _collect_function(
    compiler: Compiler,
    library: str,
    node: gast.ASTRef,
) -> FunctionSymbol | None:
    name = _identifier(node)
    if not name:
        compiler.error('La declaracion extern no tiene nombre')
        return None
    if name == 'main':
        compiler.error('Una declaracion extern no puede usar el nombre main')
        return None

    parameters_node = next(
        (
            child for child in _children(node)
            if isinstance(child, gast.ASTRef) and child.name == 'PARAMETERS'
        ),
        None,
    )
    if parameters_node is None:
        compiler.error(f'La declaracion extern {name} no tiene parametros validos')
        return None

    try:
        parameters = tuple(
            _parameter_spec(pair)
            for pair in _parameter_items(parameters_node)
            if isinstance(pair, gast.ASTRef) and pair.name == 'PAIR_PARAM'
        )
        return_type = _return_spec(node)
        _validate_abi_type(
            compiler,
            return_type,
            f'El retorno de extern {name}',
            is_return=True,
        )
        seen: set[str] = set()
        for parameter in parameters:
            if parameter.name in seen:
                raise TypeResolutionError(
                    f'El parametro {parameter.name} esta duplicado en extern {name}'
                )
            seen.add(parameter.name)
            if parameter.has_default:
                raise TypeResolutionError(
                    f'El parametro {parameter.name} de extern {name} '
                    'no puede tener valor por defecto'
                )
            _validate_abi_type(
                compiler,
                parameter.type_spec,
                f'El parametro {parameter.name} de extern {name}',
            )
    except TypeResolutionError as error:
        compiler.error(str(error))
        return None

    symbol = FunctionSymbol(
        name,
        FunctionSignature(parameters=parameters, return_type=return_type),
        external_library=library,
    )
    if not compiler.storage.define_function(symbol):
        compiler.error(f'La funcion ya fue declarada: {name}')
        return None
    return symbol


def collect(compiler: Compiler, node: gast.ASTRef) -> None:
    library_value = _string_value(node)
    if library_value is None:
        compiler.error(
            'La declaracion extern requiere una libreria: extern "library":'
        )
        return

    try:
        library = _normalize_library(library_value)
    except TypeResolutionError as error:
        compiler.error(str(error))
        return

    body = _extern_body(node)
    if body is None:
        compiler.error(f'La declaracion extern {library} no tiene cuerpo')
        return

    symbols = [
        symbol
        for function_node in _extern_functions(body)
        if (symbol := _collect_function(compiler, library, function_node)) is not None
    ]
    if symbols and library not in compiler.storage.native_links:
        compiler.storage.native_links.append(library)


__all__ = ['collect']

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gram import ast as gast
from gram.core.lexer import Token

from core.frontend.HEADERS.headers.tools.common import (
    FunctionSpecifierHandler,
    IssueSeverity,
    QualifierHandler,
    SemanticDiagnostics,
    StorageSpecifierHandler,
    TypeSpecifierHandler,
    extract_ast_tokens,
    find_ast_nodes,
)
from core.frontend.HEADERS.headers.tools.var_type_resolution import _collect_specifiers, _extract_pointer_levels


@dataclass
class ResolvedParameter:
    # Representacion semantica de un parametro formal de funcion
    name: str | None
    type_str: str
    is_variadic: bool = False
    is_void: bool = False
    qualifiers: list[str] = field(default_factory=list)
    pointer_level: int = 0
    array_dimension: str | None = None


@dataclass
class ResolvedFunction:
    # Representacion semantica resuelta de una declaracion de funcion
    name: str
    return_type: str
    return_pointer_level: int = 0
    storage_classes: list[str] = field(default_factory=list)
    return_qualifiers: list[str] = field(default_factory=list)
    function_specifiers: list[str] = field(default_factory=list)
    calling_convention: str | None = None
    parameters: list[ResolvedParameter] = field(default_factory=list)
    is_variadic: bool = False
    returns_function_pointer: bool = False


class FuncReturnTypeHandler:
    # Validador semantico del tipo de retorno de funciones

    @classmethod
    def validate_return_type(
        cls,
        base_type: str,
        pointer_levels: int,
        is_returning_array: bool,
        is_returning_func: bool,
        qualifiers: list[str],
        diag: SemanticDiagnostics,
        func_name: str
    ) -> None:
        # En C una funcion no puede retornar directamente una funcion o un arreglo
        if is_returning_func and pointer_levels == 0:
            diag.add_error("FUNC-RET-FUNC", f"La funcion '{func_name}' no puede retornar directamente una funcion (debe retornar un puntero a funcion)")

        if is_returning_array and pointer_levels == 0:
            diag.add_error("FUNC-RET-ARRAY", f"La funcion '{func_name}' no puede retornar directamente un arreglo (debe retornar un puntero)")

        # _Atomic no puede calificar el tipo de retorno de una funcion
        if "_Atomic" in qualifiers:
            diag.add_error("FUNC-RET-ATOMIC", f"El tipo de retorno de la funcion '{func_name}' no puede estar calificado como '_Atomic'")

        # Detectar calificadores duplicados en el retorno
        QualifierHandler.check_duplicates(qualifiers, diag, f"tipo de retorno de '{func_name}'")


class FuncStorageHandler:
    # Validador de clases de almacenamiento para declaraciones de funcion

    ALLOWED_FUNC_STORAGE = {"extern", "static"}

    @classmethod
    def validate_storage(cls, storage_specs: list[str], diag: SemanticDiagnostics, func_name: str) -> list[str]:
        # Las funciones solo pueden tener almacenamiento extern o static
        StorageSpecifierHandler.check_mutual_exclusions(storage_specs, diag, f"funcion '{func_name}'")
        for s in storage_specs:
            if s not in cls.ALLOWED_FUNC_STORAGE:
                diag.add_error("FUNC-STORAGE-INVALID", f"La clase de almacenamiento '{s}' no esta permitida en la funcion '{func_name}'", s)
        return list(dict.fromkeys(storage_specs))


class FuncSpecifierHandler:
    # Validador de especificadores de funcion (inline, _Noreturn) y convenciones de llamada

    @classmethod
    def validate_specifiers(cls, raw_specs: list[str], diag: SemanticDiagnostics, func_name: str) -> tuple[list[str], str | None]:
        # Valida duplicados y colisiones de convenciones de llamada
        cconv = FunctionSpecifierHandler.check_calling_conventions(raw_specs, diag, f"funcion '{func_name}'")
        fspecs = [s for s in raw_specs if s in ("inline", "_Noreturn", "__inline", "__inline__", "__forceinline")]
        return list(dict.fromkeys(fspecs)), cconv


class FuncParamsHandler:
    # Validador semantico de la lista de parametros formales de una funcion

    @classmethod
    def validate_parameters(cls, params: list[ResolvedParameter], diag: SemanticDiagnostics, func_name: str) -> None:
        # Valida reglas de parametros en C estandar
        if not params:
            return

        # 1. Si hay void, debe ser el unico parametro
        has_void = any(p.is_void for p in params)
        if has_void and len(params) > 1:
            diag.add_error("FUNC-PARAM-VOID-MULTI", f"'void' debe ser el unico parametro formal en la funcion '{func_name}'")

        # 2. El parametro variadico (...) debe ser siempre el ultimo
        for idx, param in enumerate(params):
            if param.is_variadic and idx != len(params) - 1:
                diag.add_error("FUNC-PARAM-VA-POSITION", f"El parametro variadico '...' debe encontrarse al final en la funcion '{func_name}'")


def _extract_parameters(params_node: Any, diag: SemanticDiagnostics, func_name: str) -> tuple[list[ResolvedParameter], bool]:
    # Extrae y valida la lista de parametros desde el AST
    resolved_params: list[ResolvedParameter] = []
    is_variadic = False

    if params_node is None:
        return resolved_params, is_variadic

    param_nodes = find_ast_nodes(params_node, "PARAM")
    for p in param_nodes:
        tokens = [str(t.value) for t in extract_ast_tokens(p)]
        if not tokens:
            continue

        if "..." in tokens:
            is_variadic = True
            resolved_params.append(ResolvedParameter(name=None, type_str="...", is_variadic=True))
            continue

        if tokens == ["void"]:
            resolved_params.append(ResolvedParameter(name=None, type_str="void", is_void=True))
            continue

        # Parametro estandar
        p_name = None
        ident_tokens = [str(t.value) for t in extract_ast_tokens(p) if t.token == Token.IDENT]
        if ident_tokens:
            p_name = ident_tokens[-1]

        # Comprobar niveles de puntero en el parametro
        ptr_count = sum(1 for t in tokens if t == "*")
        quals = [t for t in tokens if t in ("const", "volatile", "restrict", "_Atomic")]

        type_tokens = [t for t in tokens if t not in ("*", p_name) and t not in quals]
        type_str = " ".join(type_tokens) if type_tokens else "int"

        resolved_params.append(
            ResolvedParameter(
                name=p_name,
                type_str=type_str,
                qualifiers=quals,
                pointer_level=ptr_count,
            )
        )

    # Validar reglas de parametros
    FuncParamsHandler.validate_parameters(resolved_params, diag, func_name)
    return resolved_params, is_variadic


def resolve_func_declaration(func_decl_node: gast.ASTRef, diag: SemanticDiagnostics | None = None) -> ResolvedFunction | None:
    # Resuelve y valida semanticamente una declaracion de funcion completa
    if diag is None:
        diag = SemanticDiagnostics()

    if not isinstance(func_decl_node, gast.ASTRef):
        raise TypeError(f"Se esperaba ASTRef para FUNC_DECL, pero se recibio {type(func_decl_node).__name__}")
    if func_decl_node.name != "FUNC_DECL":
        raise ValueError(f"Se esperaba nodo FUNC_DECL, pero se recibio {func_decl_node.name}")
    if len(func_decl_node.nodes) < 2:
        raise ValueError(f"Nodo FUNC_DECL incompleto: contiene {len(func_decl_node.nodes)} nodos hijos")

    decl_specifiers_node = func_decl_node.nodes[0]
    func_declarator_node = func_decl_node.nodes[1]

    # 1. Clasificar especificadores
    raw_storage, raw_qualifiers, raw_func_specs, _, type_spec_node = _collect_specifiers(decl_specifiers_node)

    # 2. Extraer nombre de la funcion y sus parametros
    func_ident_nodes = find_ast_nodes(func_declarator_node, "FUNC_IDENT")
    if func_ident_nodes:
        ident_toks = [str(t.value) for t in extract_ast_tokens(func_ident_nodes[0]) if t.token == Token.IDENT]
        func_name = ident_toks[-1] if ident_toks else "unknown_fn"
    else:
        all_tokens = extract_ast_tokens(func_declarator_node)
        idents = [str(t.value) for t in all_tokens if t.token == Token.IDENT]
        func_name = idents[0] if idents else "unknown_fn"

    # 3. Validar clases de almacenamiento
    storage = FuncStorageHandler.validate_storage(raw_storage, diag, func_name)

    # 4. Validar especificadores de funcion y convenciones de llamada
    fspecs, cconv = FuncSpecifierHandler.validate_specifiers(raw_func_specs, diag, func_name)

    # 5. Extraer punteros en el retorno
    pointer_nodes = find_ast_nodes(func_declarator_node, "POINTER")
    return_ptr_levels = len(_extract_pointer_levels(pointer_nodes[0], diag, func_name)) if pointer_nodes else 0

    # 6. Extraer y validar parametros
    params_nodes = find_ast_nodes(func_declarator_node, "PARAMS")
    params_node = params_nodes[0] if params_nodes else None
    params, is_va = _extract_parameters(params_node, diag, func_name)

    # 7. Resolver tipo de retorno
    return_type = "int"
    if type_spec_node:
        return_type = TypeSpecifierHandler.validate_basic_type_composition(
            [str(t.value) for t in extract_ast_tokens(type_spec_node)], diag, f"retorno de '{func_name}'"
        )

    # 8. Validar reglas del tipo de retorno
    FuncReturnTypeHandler.validate_return_type(
        base_type=return_type,
        pointer_levels=return_ptr_levels,
        is_returning_array=False,
        is_returning_func=False,
        qualifiers=raw_qualifiers,
        diag=diag,
        func_name=func_name
    )

    return ResolvedFunction(
        name=func_name,
        return_type=return_type,
        return_pointer_level=return_ptr_levels,
        storage_classes=storage,
        return_qualifiers=raw_qualifiers,
        function_specifiers=fspecs,
        calling_convention=cconv,
        parameters=params,
        is_variadic=is_va,
    )


def validate(compiler: Any, node: gast.ASTRef) -> tuple[str, ResolvedFunction | None]:
    # Punto de entrada de validacion compatible con el compilador
    diag = SemanticDiagnostics()
    fn = resolve_func_declaration(node, diag)

    name = fn.name if fn else "unknown_fn"
    for issue in diag.issues:
        msg = f"[{issue.code}] {issue.message}"
        if issue.severity == IssueSeverity.ERROR:
            compiler.error(msg)
        elif issue.severity == IssueSeverity.WARNING:
            compiler.advice(msg)

    return name, fn


__all__ = [
    'FuncParamsHandler',
    'FuncReturnTypeHandler',
    'FuncSpecifierHandler',
    'FuncStorageHandler',
    'ResolvedFunction',
    'ResolvedParameter',
    'resolve_func_declaration',
    'validate',
]

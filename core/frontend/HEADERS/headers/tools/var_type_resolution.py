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


@dataclass
class ResolvedPointerLevel:
    # Nivel de indireccion de puntero y sus calificadores asociados
    level: int
    qualifiers: list[str] = field(default_factory=list)
    calling_convention: str | None = None


@dataclass
class ResolvedVariable:
    # Representacion semantica resuelta de una variable declarada
    name: str
    base_type: str
    storage_classes: list[str] = field(default_factory=list)
    qualifiers: list[str] = field(default_factory=list)
    pointer_levels: list[ResolvedPointerLevel] = field(default_factory=list)
    array_dimensions: list[str] = field(default_factory=list)
    alignment: str | None = None
    has_initializer: bool = False
    is_function_pointer: bool = False
    attributes: list[str] = field(default_factory=list)

    @property
    def is_pointer(self) -> bool:
        # Indica si la variable es de tipo puntero
        return len(self.pointer_levels) > 0

    @property
    def is_const(self) -> bool:
        # Indica si el tipo base tiene calificador const
        return "const" in self.qualifiers


class VarQualifierHandler:
    # Handler especializado en resolver calificadores para variables

    @classmethod
    def resolve_base_qualifiers(cls, raw_qualifiers: list[str], is_pointer: bool, is_array: bool, diag: SemanticDiagnostics, var_name: str) -> list[str]:
        # Valida duplicados y combinaciones imposibles de calificadores en el tipo base
        normalized = QualifierHandler.check_duplicates(raw_qualifiers, diag, f"variable '{var_name}'")
        QualifierHandler.check_combinations(normalized, is_pointer=is_pointer, is_function=False, is_array=is_array, diag=diag, ctx=f"variable '{var_name}'")
        return normalized

    @classmethod
    def resolve_pointer_qualifiers(cls, raw_qualifiers: list[str], diag: SemanticDiagnostics, level: int, var_name: str) -> list[str]:
        # Valida calificadores aplicados directamente a un nivel de puntero (* const * restrict)
        normalized = QualifierHandler.check_duplicates(raw_qualifiers, diag, f"puntero nivel {level} de '{var_name}'")
        # En un puntero, restrict siempre es valido
        QualifierHandler.check_combinations(normalized, is_pointer=True, is_function=False, is_array=False, diag=diag, ctx=f"puntero nivel {level} de '{var_name}'")
        return normalized


class VarStorageHandler:
    # Handler especializado en resolver la clase de almacenamiento de una variable

    @classmethod
    def resolve_storage(cls, raw_storage: list[str], diag: SemanticDiagnostics, var_name: str) -> list[str]:
        # Valida duplicados y exclusiones mutuas de almacenamiento
        StorageSpecifierHandler.check_mutual_exclusions(raw_storage, diag, f"variable '{var_name}'")
        return list(dict.fromkeys(raw_storage))

    @classmethod
    def validate_initializer_coherence(cls, storage: list[str], qualifiers: list[str], has_init: bool, diag: SemanticDiagnostics, var_name: str) -> None:
        # Verifica coherencia entre almacenamiento/calificadores e inicializador
        if "constexpr" in storage and not has_init:
            diag.add_error("VAR-CONSTEXPR-NOINIT", f"La variable 'constexpr' '{var_name}' requiere un inicializador obligatorio")

        if "extern" in storage and has_init:
            diag.add_warning("VAR-EXTERN-INIT", f"La variable 'extern' '{var_name}' esta siendo inicializada en un archivo de cabecera")

        if "const" in qualifiers and "extern" not in storage and not has_init:
            diag.add_warning("VAR-CONST-UNINIT", f"La variable 'const' '{var_name}' no posee inicializador")


class VarTypeHandler:
    # Handler para extraer y componer el tipo de dato de una variable

    @classmethod
    def resolve_type_specifier(cls, type_spec_node: gast.ASTRef | None, diag: SemanticDiagnostics, var_name: str) -> str:
        # Extrae los tokens del especificador de tipo y valida su composicion
        if type_spec_node is None:
            diag.add_error("VAR-TYPE-NONE", f"No se pudo determinar el tipo base para '{var_name}'")
            return "int"

        tokens = [str(t.value) for t in extract_ast_tokens(type_spec_node)]
        if not tokens:
            diag.add_error("VAR-TYPE-NONE", f"No se pudo determinar el tipo base para '{var_name}'")
            return "int"

        first = tokens[0]
        if first in ("struct", "union", "enum") or first.startswith("_Atomic") or first.startswith("typeof"):
            return " ".join(tokens)

        return TypeSpecifierHandler.validate_basic_type_composition(tokens, diag, f"variable '{var_name}'")


def _collect_specifiers(decl_specifiers_node: gast.ASTRef) -> tuple[list[str], list[str], list[str], list[str], gast.ASTRef | None]:
    # Clasifica los prefijos de especificadores en almacenamiento, calificadores, funciones y alineacion
    if not isinstance(decl_specifiers_node, gast.ASTRef):
        raise TypeError(f"Se esperaba ASTRef para DECL_SPECIFIERS, pero se recibio {type(decl_specifiers_node).__name__}")
    if decl_specifiers_node.name != "DECL_SPECIFIERS":
        raise ValueError(f"Se esperaba nodo DECL_SPECIFIERS, pero se recibio {decl_specifiers_node.name}")

    storage = [str(t.value) for n in find_ast_nodes(decl_specifiers_node, "STORAGE_SPECIFIER") for t in extract_ast_tokens(n)]
    qualifiers = [str(t.value) for n in (find_ast_nodes(decl_specifiers_node, "QUALIFIER") + find_ast_nodes(decl_specifiers_node, "ATOMIC_QUALIFIER")) for t in extract_ast_tokens(n)]
    func_specs = [str(t.value) for n in find_ast_nodes(decl_specifiers_node, "FUNCTION_SPECIFIER") for t in extract_ast_tokens(n)]
    alignas_specs = [str(t.value) for n in find_ast_nodes(decl_specifiers_node, "ALIGNAS_SPECIFIER") for t in extract_ast_tokens(n)]
    type_spec_nodes = find_ast_nodes(decl_specifiers_node, "TYPE_SPEC")
    type_spec_node = type_spec_nodes[0] if type_spec_nodes else None

    return storage, qualifiers, func_specs, alignas_specs, type_spec_node


def _extract_pointer_levels(pointer_node: gast.ASTRef | None, diag: SemanticDiagnostics, var_name: str) -> list[ResolvedPointerLevel]:
    # Extrae recursivamente los niveles de puntero y sus calificadores
    levels: list[ResolvedPointerLevel] = []
    if pointer_node is None:
        return levels
    if not isinstance(pointer_node, gast.ASTRef):
        raise TypeError(f"Se esperaba ASTRef para POINTER, pero se recibio {type(pointer_node).__name__}")

    part_nodes = find_ast_nodes(pointer_node, "POINTER_PART")
    for idx, part in enumerate(part_nodes):
        part_tokens = [str(t.value) for t in extract_ast_tokens(part)]
        quals = [t for t in part_tokens if t in ("const", "volatile", "restrict", "_Atomic", "__const", "__volatile", "__restrict")]
        cconvs = [t for t in part_tokens if t in ("__stdcall", "__cdecl", "__fastcall", "__thiscall")]

        norm_quals = VarQualifierHandler.resolve_pointer_qualifiers(quals, diag, idx + 1, var_name)
        cconv = cconvs[0] if cconvs else None
        levels.append(ResolvedPointerLevel(level=idx + 1, qualifiers=norm_quals, calling_convention=cconv))

    return levels


def _extract_declarator_info(var_declarator_node: gast.ASTRef, diag: SemanticDiagnostics) -> tuple[str, list[ResolvedPointerLevel], list[str], bool, bool]:
    # Extrae el identificador, punteros, dimensiones de arreglo e inicializador de un declarador
    if not isinstance(var_declarator_node, gast.ASTRef):
        raise TypeError(f"Se esperaba ASTRef para VAR_DECLARATOR, pero se recibio {type(var_declarator_node).__name__}")

    # 1. Identificador
    idents = [str(t.value) for t in extract_ast_tokens(var_declarator_node) if t.token == Token.IDENT]
    var_name = idents[0] if idents else "unknown"

    # 2. Punteros
    pointer_nodes = find_ast_nodes(var_declarator_node, "POINTER")
    pointer_levels = _extract_pointer_levels(pointer_nodes[0], diag, var_name) if pointer_nodes else []

    # 3. Dimensiones de arreglo
    array_dim_nodes = find_ast_nodes(var_declarator_node, "ARRAY_DIMENSION")
    array_dims = ["".join(str(t.value) for t in extract_ast_tokens(dim)) for dim in array_dim_nodes]

    # 4. Puntero a funcion
    is_func_ptr = bool(find_ast_nodes(var_declarator_node, "PARAMS"))

    # 5. Inicializador
    has_initializer = any(t.token == Token.ASSIGN for t in extract_ast_tokens(var_declarator_node))

    return var_name, pointer_levels, array_dims, has_initializer, is_func_ptr


def resolve_var_declaration(var_decl_node: gast.ASTRef, diag: SemanticDiagnostics | None = None) -> list[ResolvedVariable]:
    # Resuelve y valida semanticamente un nodo VAR_DECL retornando las variables declaradas
    if diag is None:
        diag = SemanticDiagnostics()

    if not isinstance(var_decl_node, gast.ASTRef):
        raise TypeError(f"Se esperaba ASTRef para VAR_DECL, pero se recibio {type(var_decl_node).__name__}")
    if var_decl_node.name != "VAR_DECL":
        raise ValueError(f"Se esperaba nodo VAR_DECL, pero se recibio {var_decl_node.name}")
    if len(var_decl_node.nodes) < 2:
        raise ValueError(f"Nodo VAR_DECL incompleto: tiene {len(var_decl_node.nodes)} nodos hijos")

    decl_specifiers_node = var_decl_node.nodes[0]
    declarators_node = var_decl_node.nodes[1]

    # 1. Extraer y clasificar especificadores
    raw_storage, raw_qualifiers, raw_func_specs, align_specs, type_spec_node = _collect_specifiers(decl_specifiers_node)

    # 2. Obtener lista de declaradores
    if isinstance(declarators_node, gast.ArrayNode):
        declarator_nodes = list(declarators_node.items)
    elif isinstance(declarators_node, (list, tuple)):
        declarator_nodes = list(declarators_node)
    elif isinstance(declarators_node, gast.ASTRef):
        declarator_nodes = [declarators_node]
    else:
        raise TypeError(f"Tipo inesperado para declaradores en VAR_DECL: {type(declarators_node).__name__}")

    resolved_vars: list[ResolvedVariable] = []

    for decl_node in declarator_nodes:
        name, ptr_levels, array_dims, has_init, is_func_ptr = _extract_declarator_info(decl_node, diag)
        storage = VarStorageHandler.resolve_storage(raw_storage, diag, name)
        FunctionSpecifierHandler.check_applicability(raw_func_specs, is_function=is_func_ptr, diag=diag, ctx=f"variable '{name}'")
        is_ptr = len(ptr_levels) > 0
        is_arr = len(array_dims) > 0
        qualifiers = VarQualifierHandler.resolve_base_qualifiers(raw_qualifiers, is_pointer=is_ptr, is_array=is_arr, diag=diag, var_name=name)
        VarStorageHandler.validate_initializer_coherence(storage, qualifiers, has_init, diag, name)
        base_type = VarTypeHandler.resolve_type_specifier(type_spec_node, diag, name)
        alignment = align_specs[0] if align_specs else None

        resolved = ResolvedVariable(
            name=name,
            base_type=base_type,
            storage_classes=storage,
            qualifiers=qualifiers,
            pointer_levels=ptr_levels,
            array_dimensions=array_dims,
            alignment=alignment,
            has_initializer=has_init,
            is_function_pointer=is_func_ptr,
        )
        resolved_vars.append(resolved)

    return resolved_vars


def validate(compiler: Any, node: gast.ASTRef) -> list[tuple[str, ResolvedVariable]]:
    # Punto de entrada de validacion compatible con el compilador
    diag = SemanticDiagnostics()
    vars_resolved = resolve_var_declaration(node, diag)

    # Transferir errores al compilador si existe telemetria activa
    for issue in diag.issues:
        msg = f"[{issue.code}] {issue.message}"
        if issue.severity == IssueSeverity.ERROR:
            compiler.error(msg)
        elif issue.severity == IssueSeverity.WARNING:
            compiler.advice(msg)

    return [(v.name, v) for v in vars_resolved]

    return [(v.name, v) for v in vars_resolved]


__all__ = [
    'ResolvedPointerLevel',
    'ResolvedVariable',
    'VarQualifierHandler',
    'VarStorageHandler',
    'VarTypeHandler',
    'resolve_var_declaration',
    'validate',
]

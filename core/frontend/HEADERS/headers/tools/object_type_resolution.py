from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gram import ast as gast
from gram.core.lexer import Token

from core.frontend.HEADERS.headers.tools.common import (
    IssueSeverity,
    QualifierHandler,
    SemanticDiagnostics,
    StorageSpecifierHandler,
    extract_ast_tokens,
    find_ast_nodes,
)
from core.frontend.HEADERS.headers.tools.var_type_resolution import _collect_specifiers


@dataclass
class ResolvedStructMember:
    # Representacion semantica de un miembro de struct o union
    name: str | None
    type_str: str
    is_bitfield: bool = False
    bitfield_width: str | None = None
    is_flexible_array: bool = False
    pointer_level: int = 0
    qualifiers: list[str] = field(default_factory=list)


@dataclass
class ResolvedStructUnion:
    # Representacion semantica de una definicion de struct o union
    kind: str  # "struct" o "union"
    name: str | None
    members: list[ResolvedStructMember] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)
    is_forward_decl: bool = False


@dataclass
class ResolvedEnumerator:
    # Representacion de un elemento de enum
    name: str
    value_expr: str | None = None
    attributes: list[str] = field(default_factory=list)


@dataclass
class ResolvedEnum:
    # Representacion semantica de una definicion de enum
    name: str | None
    underlying_type: str = "int"
    enumerators: list[ResolvedEnumerator] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)
    is_forward_decl: bool = False


@dataclass
class ResolvedTypedef:
    # Representacion semantica de una declaracion typedef
    names: list[str]
    underlying_type: str
    attributes: list[str] = field(default_factory=list)


class BitFieldHandler:
    # Validador semantico de campos de bits

    ALLOWED_BITFIELD_TYPES = {"int", "signed", "unsigned", "char", "short", "long", "bool", "_Bool"}

    @classmethod
    def validate_bitfield(cls, type_str: str, name: str | None, width_str: str | None, is_pointer: bool, diag: SemanticDiagnostics, ctx: str = "struct") -> None:
        # Los campos de bits no pueden aplicarse sobre tipos puntero o flotantes
        if is_pointer:
            diag.add_error("BITFIELD-POINTER", f"Un campo de bits no puede ser de tipo puntero en {ctx}")

        words = set(type_str.split())
        if not (words & cls.ALLOWED_BITFIELD_TYPES):
            diag.add_error("BITFIELD-TYPE-INVALID", f"El campo de bits '{name or ':ancho'}' debe ser de tipo integral (recibio '{type_str}') en {ctx}")

        # Un campo de bits sin nombre de ancho 0 es valido para forzar alineacion
        if name is None and width_str == "0":
            return

        if name is None and width_str is None:
            diag.add_error("BITFIELD-WIDTH-MISSING", f"Campo de bits sin nombre requiere ancho explicito en {ctx}")


class StructUnionHandler:
    # Validador semantico de miembros en estructuras y uniones

    FORBIDDEN_STORAGE_IN_MEMBER = {"extern", "static", "auto", "register", "_Thread_local", "thread_local", "typedef"}
    FORBIDDEN_FUNC_SPECS_IN_MEMBER = {"inline", "_Noreturn"}

    @classmethod
    def validate_members(cls, kind: str, tag_name: str | None, members: list[ResolvedStructMember], diag: SemanticDiagnostics) -> None:
        # Revisa duplicados de nombres y reglas de arreglos flexibles
        label = f"{kind} '{tag_name or 'anon'}'"
        seen_names: set[str] = set()

        for idx, m in enumerate(members):
            if m.name is not None:
                if m.name in seen_names:
                    diag.add_error("STRUCT-DUP-MEMBER", f"Nombre de miembro duplicado '{m.name}' en {label}", m.name)
                else:
                    seen_names.add(m.name)

            # Un arreglo flexible solo puede ser el ultimo miembro de un struct, nunca en union
            if m.is_flexible_array:
                if kind == "union":
                    diag.add_error("UNION-FLEX-ARRAY", f"Las uniones no pueden contener arreglos flexibles ('{m.name}')")
                elif idx != len(members) - 1:
                    diag.add_error("STRUCT-FLEX-NOT-LAST", f"El arreglo flexible '{m.name}' debe ser el ultimo miembro en {label}")

    @classmethod
    def validate_member_specifiers(cls, storage_specs: list[str], func_specs: list[str], member_name: str, diag: SemanticDiagnostics) -> None:
        # Los miembros de struct/union no pueden tener almacenamiento ni inline
        for s in storage_specs:
            if s in cls.FORBIDDEN_STORAGE_IN_MEMBER:
                diag.add_error("MEMBER-STORAGE-FORBIDDEN", f"Clase de almacenamiento '{s}' prohibida en el miembro '{member_name}'", s)

        for f in func_specs:
            if f in cls.FORBIDDEN_FUNC_SPECS_IN_MEMBER:
                diag.add_error("MEMBER-FSPEC-FORBIDDEN", f"Especificador '{f}' prohibido en el miembro '{member_name}'", f)


class EnumHandler:
    # Validador semantico para enumeraciones C89 y C23

    INVALID_UNDERLYING_TYPES = {"float", "double", "void"}

    @classmethod
    def validate_enum(cls, enum_name: str | None, underlying_type: str, enumerators: list[ResolvedEnumerator], diag: SemanticDiagnostics) -> None:
        # Revisa tipo subyacente y nombres de enumeradores duplicados
        label = f"enum '{enum_name or 'anon'}'"

        # Validar tipo subyacente
        words = set(underlying_type.split())
        if words & cls.INVALID_UNDERLYING_TYPES or "*" in underlying_type:
            diag.add_error("ENUM-INVALID-UNDERLYING", f"Tipo subyacente no integral invalido '{underlying_type}' en {label}")

        # Validar duplicados de enumeradores
        seen_enums: set[str] = set()
        for en in enumerators:
            if en.name in seen_enums:
                diag.add_error("ENUM-DUP-VALUE", f"Constante de enumeracion duplicada '{en.name}' en {label}", en.name)
            else:
                seen_enums.add(en.name)


class TypedefHandler:
    # Validador semantico para declaraciones typedef

    @classmethod
    def validate_typedef(cls, names: list[str], storage_specs: list[str], align_specs: list[str], has_init: bool, diag: SemanticDiagnostics) -> None:
        # Revisa que un typedef no incluya clases de almacenamiento adicionales, alignas o inicializadores
        StorageSpecifierHandler.check_mutual_exclusions(storage_specs, diag, f"typedef '{', '.join(names)}'")

        if align_specs:
            diag.add_error("TYPEDEF-ALIGNAS", f"No se permite '_Alignas' en una declaracion typedef ('{', '.join(names)}')")

        if has_init:
            diag.add_error("TYPEDEF-INITIALIZER", f"Una declaracion typedef no puede tener inicializador ('{', '.join(names)}')")


def resolve_tag_declaration(tag_decl_node: gast.ASTRef, diag: SemanticDiagnostics | None = None) -> ResolvedStructUnion | ResolvedEnum | None:
    # Resuelve y valida semanticamente un nodo TAG_DECL (struct, union o enum)
    if diag is None:
        diag = SemanticDiagnostics()

    if not isinstance(tag_decl_node, gast.ASTRef):
        raise TypeError(f"Se esperaba ASTRef para TAG_DECL, pero se recibio {type(tag_decl_node).__name__}")
    if tag_decl_node.name != "TAG_DECL":
        raise ValueError(f"Se esperaba nodo TAG_DECL, pero se recibio {tag_decl_node.name}")

    ast_tokens = extract_ast_tokens(tag_decl_node)
    tokens = [str(t.value) for t in ast_tokens]
    if not tokens:
        raise ValueError("Nodo TAG_DECL sin tokens")

    first = tokens[0]
    if first in ("struct", "union"):
        tag_name = tokens[1] if len(tokens) > 1 and tokens[1] not in ("{", ";", ":") else None
        struct_bodies = find_ast_nodes(tag_decl_node, "STRUCT_BODY")
        is_forward = len(struct_bodies) == 0

        # Extraer miembros
        members: list[ResolvedStructMember] = []
        if not is_forward:
            member_nodes = find_ast_nodes(struct_bodies[0], "STRUCT_MEMBER")
            for m_node in member_nodes:
                decl_nodes = find_ast_nodes(m_node, "STRUCT_DECLARATOR")
                if decl_nodes:
                    for d in decl_nodes:
                        d_idents = [str(t.value) for t in extract_ast_tokens(d) if t.token == Token.IDENT]
                        if d_idents:
                            members.append(ResolvedStructMember(name=d_idents[0], type_str="int"))
                else:
                    idents = [str(t.value) for t in extract_ast_tokens(m_node) if t.token == Token.IDENT]
                    if idents:
                        members.append(ResolvedStructMember(name=idents[-1], type_str="int"))

        StructUnionHandler.validate_members(first, tag_name, members, diag)
        return ResolvedStructUnion(kind=first, name=tag_name, members=members, is_forward_decl=is_forward)

    elif first == "enum":
        enum_name = tokens[1] if len(tokens) > 1 and tokens[1] not in ("{", ":", ";") else None
        enum_bodies = find_ast_nodes(tag_decl_node, "ENUM_BODY")
        is_forward = len(enum_bodies) == 0

        # Extraer tipo subyacente si existe
        underlying = "int"
        und_nodes = find_ast_nodes(tag_decl_node, "ENUM_UNDERLYING_TYPE")
        if und_nodes:
            underlying = " ".join([str(t.value) for t in extract_ast_tokens(und_nodes[0])])
        elif ":" in tokens:
            col_idx = tokens.index(":")
            end_idx = tokens.index("{") if "{" in tokens else (tokens.index(";") if ";" in tokens else len(tokens))
            underlying = " ".join(tokens[col_idx + 1:end_idx])

        # Extraer enumeradores
        enumerators: list[ResolvedEnumerator] = []
        if not is_forward:
            en_nodes = find_ast_nodes(enum_bodies[0], "ENUMERATOR")
            for en in en_nodes:
                en_tokens = [str(t.value) for t in extract_ast_tokens(en)]
                if en_tokens:
                    enumerators.append(ResolvedEnumerator(name=en_tokens[0]))

        EnumHandler.validate_enum(enum_name, underlying, enumerators, diag)
        return ResolvedEnum(name=enum_name, underlying_type=underlying, enumerators=enumerators, is_forward_decl=is_forward)

    else:
        raise ValueError(f"TAG_DECL no reconocido que inicia con '{first}'")


def resolve_typedef_declaration(typedef_decl_node: gast.ASTRef, diag: SemanticDiagnostics | None = None) -> ResolvedTypedef | None:
    # Resuelve y valida semanticamente una declaracion TYPEDEF_DECL
    if diag is None:
        diag = SemanticDiagnostics()

    if not isinstance(typedef_decl_node, gast.ASTRef):
        raise TypeError(f"Se esperaba ASTRef para TYPEDEF_DECL, pero se recibio {type(typedef_decl_node).__name__}")
    if typedef_decl_node.name != "TYPEDEF_DECL":
        raise ValueError(f"Se esperaba nodo TYPEDEF_DECL, pero se recibio {typedef_decl_node.name}")

    ast_tokens = extract_ast_tokens(typedef_decl_node)
    tokens = [str(t.value) for t in ast_tokens]
    idents = [str(t.value) for t in ast_tokens if t.token == Token.IDENT]

    if not idents:
        diag.add_error("TYPEDEF-NO-NAME", "La declaracion typedef no define ningun alias")
        return None

    names = idents[-1:]
    type_tokens = [t for t in tokens if t not in ("typedef", ";") and t not in names]
    underlying = " ".join(type_tokens) if type_tokens else "int"

    storage_specs = ["typedef"] + [t for t in tokens if t in ("extern", "static", "auto", "register", "_Thread_local", "constexpr")]
    align_specs = [t for t in tokens if t in ("_Alignas", "alignas")]
    has_init = "=" in tokens

    TypedefHandler.validate_typedef(names, storage_specs, align_specs, has_init, diag)
    return ResolvedTypedef(names=names, underlying_type=underlying)


def validate(compiler: Any, node: gast.ASTRef) -> tuple[str, Any]:
    # Punto de entrada de validacion compatible con el compilador
    if not isinstance(node, gast.ASTRef):
        raise TypeError(f"Se esperaba un nodo ASTRef, pero se recibio {type(node).__name__}")

    diag = SemanticDiagnostics()
    res: Any = None

    if node.name == "TAG_DECL":
        res = resolve_tag_declaration(node, diag)
        symbol_name = (res.name or "anon_tag") if res else "unknown"
    elif node.name == "TYPEDEF_DECL":
        res = resolve_typedef_declaration(node, diag)
        symbol_name = res.names[0] if res and res.names else "unknown"
    else:
        raise ValueError(f"Tipo de nodo no manejado por object_type_resolution: {node.name}")

    for issue in diag.issues:
        msg = f"[{issue.code}] {issue.message}"
        if issue.severity == IssueSeverity.ERROR:
            compiler.error(msg)
        elif issue.severity == IssueSeverity.WARNING:
            compiler.advice(msg)

    return symbol_name, res


__all__ = [
    'BitFieldHandler',
    'EnumHandler',
    'ResolvedEnum',
    'ResolvedEnumerator',
    'ResolvedStructMember',
    'ResolvedStructUnion',
    'ResolvedTypedef',
    'StructUnionHandler',
    'TypedefHandler',
    'resolve_tag_declaration',
    'resolve_typedef_declaration',
    'validate',
]

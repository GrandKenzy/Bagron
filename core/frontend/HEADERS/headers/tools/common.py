from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from gram import ast as gast
from gram.core.lexer import Token, TokenType
from tools.diagnostic import Diagnostics


class IssueSeverity(Enum):
    # Severidad del problema semantico detectado
    ERROR = "error"
    WARNING = "warning"
    ADVICE = "advice"


@dataclass
class SemanticIssue:
    # Representa un mensaje o diagnostico semantico
    severity: IssueSeverity
    code: str
    message: str
    token_value: str | None = None
    line: int | None = None
    col: int | None = None


class SemanticDiagnostics(Diagnostics):
    # Acumulador de diagnosticos semanticos para validaciones integrado con Diagnostics de EasyC
    def __init__(
        self,
        file: str = "semantic_headers",
        name: str = "SemanticHeaders",
        description: str = "Semantic validation for C headers",
    ) -> None:
        super().__init__(
            file=file,
            name=name,
            description=description,
            expose_nodes=False,
            generate_log_file=False,
        )
        self.issues: list[SemanticIssue] = []

    def add_error(self, code: str, msg: str, tok: TokenType | str | None = None) -> None:
        # Registra un error semantico y lo transmite al sistema de diagnostico base
        self._add(IssueSeverity.ERROR, code, msg, tok)
        self.error(f"[{code}] {msg}")

    def add_warning(self, code: str, msg: str, tok: TokenType | str | None = None) -> None:
        # Registra una advertencia semantica y la transmite al sistema de diagnostico base
        self._add(IssueSeverity.WARNING, code, msg, tok)
        self.advice(f"[{code}] {msg}")

    def add_advice(self, code: str, msg: str, tok: TokenType | str | None = None) -> None:
        # Registra un consejo o sugerencia semantica
        self._add(IssueSeverity.ADVICE, code, msg, tok)
        self.advice(f"[{code}] {msg}")

    def _add(self, sev: IssueSeverity, code: str, msg: str, tok: TokenType | str | None) -> None:
        val: str | None = None
        line: int | None = None
        col: int | None = None
        if isinstance(tok, TokenType):
            val = str(tok.value)
            line = tok.line
            col = tok.col
        elif tok is not None:
            val = str(tok)
        self.issues.append(SemanticIssue(sev, code, msg, val, line, col))

    @property
    def has_errors(self) -> bool:
        # Retorna True si existen errores bloqueantes
        return any(i.severity == IssueSeverity.ERROR for i in self.issues)

    @property
    def error_messages(self) -> list[str]:
        # Lista textual de errores acumulados
        return [i.message for i in self.issues if i.severity == IssueSeverity.ERROR]


# Normalizacion de calificadores equivalentes de GNU/C
NORM_QUALIFIERS: dict[str, str] = {
    "const": "const",
    "__const": "const",
    "__const__": "const",
    "volatile": "volatile",
    "__volatile": "volatile",
    "__volatile__": "volatile",
    "restrict": "restrict",
    "__restrict": "restrict",
    "__restrict__": "restrict",
    "_Atomic": "_Atomic",
}

# Normalizacion de especificadores de funcion
NORM_FUNC_SPECS: dict[str, str] = {
    "inline": "inline",
    "__inline": "inline",
    "__inline__": "inline",
    "__forceinline": "inline",
    "_Noreturn": "_Noreturn",
    "__stdcall": "__stdcall",
    "__cdecl": "__cdecl",
    "__fastcall": "__fastcall",
    "__thiscall": "__thiscall",
}

CALLING_CONVENTIONS = {"__stdcall", "__cdecl", "__fastcall", "__thiscall"}
STORAGE_CLASSES = {"extern", "static", "auto", "register", "_Thread_local", "thread_local", "constexpr", "typedef"}


class QualifierHandler:
    # Validador de calificadores (const, volatile, restrict, _Atomic)

    @staticmethod
    def normalize(qual: str) -> str:
        # Normaliza alias como __const a const
        return NORM_QUALIFIERS.get(qual, qual)

    @classmethod
    def check_duplicates(cls, qualifiers: list[str], diag: SemanticDiagnostics, ctx: str = "variable") -> list[str]:
        # Detecta calificadores duplicados y reporta advertencias
        seen: set[str] = set()
        normalized: list[str] = []
        for q in qualifiers:
            norm = cls.normalize(q)
            if norm in seen:
                diag.add_warning("QUAL-DUP", f"Calificador duplicado '{q}' en {ctx}", q)
            else:
                seen.add(norm)
                normalized.append(norm)
        return normalized

    @classmethod
    def check_combinations(
        cls,
        qualifiers: list[str],
        is_pointer: bool,
        is_function: bool,
        is_array: bool,
        diag: SemanticDiagnostics,
        ctx: str = "variable"
    ) -> None:
        # Revisa combinaciones invalidas de calificadores segun el estandar C
        norm = [cls.normalize(q) for q in qualifiers]

        # restrict solo es valido en tipos puntero a objeto
        if "restrict" in norm and not is_pointer:
            diag.add_error("QUAL-RESTRICT-NONPTR", f"El calificador 'restrict' solo puede aplicarse a tipos puntero en {ctx}", "restrict")

        # _Atomic no puede calificar funciones ni arreglos
        if "_Atomic" in norm:
            if is_function:
                diag.add_error("QUAL-ATOMIC-FUNC", f"No se permite calificar una funcion con '_Atomic' en {ctx}", "_Atomic")
            if is_array:
                diag.add_error("QUAL-ATOMIC-ARRAY", f"No se permite calificar un arreglo con '_Atomic' en {ctx}", "_Atomic")


class StorageSpecifierHandler:
    # Validador de clases de almacenamiento (static, extern, auto, register, thread_local, constexpr)

    @staticmethod
    def check_duplicates(storage_specs: list[str], diag: SemanticDiagnostics, ctx: str = "declaracion") -> list[str]:
        # Detecta clases de almacenamiento repetidas
        seen: set[str] = set()
        result: list[str] = []
        for s in storage_specs:
            if s in seen:
                diag.add_error("STORAGE-DUP", f"Clase de almacenamiento duplicada '{s}' en {ctx}", s)
            else:
                seen.add(s)
                result.append(s)
        return result

    @classmethod
    def check_mutual_exclusions(cls, storage_specs: list[str], diag: SemanticDiagnostics, ctx: str = "declaracion") -> None:
        # Valida exclusiones mutuas entre clases de almacenamiento
        specs = set(cls.check_duplicates(storage_specs, diag, ctx))

        # static y extern no pueden coexistir
        if "static" in specs and "extern" in specs:
            diag.add_error("STORAGE-STATIC-EXTERN", f"Combinacion imposible de almacenamiento: 'static' y 'extern' son mutuamente excluyentes en {ctx}")

        # auto o register no pueden combinarse con static o extern
        if ("auto" in specs or "register" in specs) and ("static" in specs or "extern" in specs):
            diag.add_error("STORAGE-AUTO-STATIC", f"Combinacion invalida de clase automatica y estatica en {ctx}")

        # typedef no puede combinarse con ninguna otra clase de almacenamiento
        if "typedef" in specs and len(specs) > 1:
            diag.add_error("STORAGE-TYPEDEF-COMBO", f"'typedef' no puede combinarse con otras clases de almacenamiento en {ctx}")

        # constexpr no puede ser extern ni thread_local
        if "constexpr" in specs:
            if "extern" in specs:
                diag.add_error("STORAGE-CONSTEXPR-EXTERN", f"'constexpr' no puede combinarse con 'extern' en {ctx}")
            if "_Thread_local" in specs or "thread_local" in specs:
                diag.add_error("STORAGE-CONSTEXPR-TLS", f"'constexpr' no puede combinarse con almacenamiento en hilo local en {ctx}")

        # Excluyendo thread_local, solo se permite como maximo una clase de almacenamiento
        base_storage = specs - {"_Thread_local", "thread_local"}
        if len(base_storage) > 1:
            diag.add_error("STORAGE-MULTIPLE", f"Multiples clases de almacenamiento incompatibles ({', '.join(base_storage)}) en {ctx}")


class FunctionSpecifierHandler:
    # Validador de especificadores de funcion y convenciones de llamada

    @classmethod
    def check_calling_conventions(cls, func_specs: list[str], diag: SemanticDiagnostics, ctx: str = "funcion") -> str | None:
        # Valida que no coexistan multiples convenciones de llamada contradictorias
        cconvs: list[str] = [NORM_FUNC_SPECS.get(s, s) for s in func_specs if s in CALLING_CONVENTIONS]
        if not cconvs:
            return None

        # Revisar duplicados
        if len(cconvs) > 1 and len(set(cconvs)) == 1:
            diag.add_warning("CCONV-DUP", f"Convencion de llamada '{cconvs[0]}' repetida en {ctx}", cconvs[0])
            return cconvs[0]

        # Revisar convenciones mutuamente excluyentes
        if len(set(cconvs)) > 1:
            diag.add_error("CCONV-CONFLICT", f"Convenciones de llamada en conflicto ({', '.join(set(cconvs))}) en {ctx}")

        return cconvs[0]

    @classmethod
    def check_applicability(cls, func_specs: list[str], is_function: bool, diag: SemanticDiagnostics, ctx: str = "variable") -> None:
        # Verifica que inline y _Noreturn no se apliquen sobre declaraciones que no sean funciones
        if is_function:
            return

        for s in func_specs:
            norm = NORM_FUNC_SPECS.get(s, s)
            if norm in ("inline", "_Noreturn"):
                diag.add_error("FSPEC-NONFUNC", f"Especificador de funcion '{s}' no permitido en {ctx}", s)
            elif norm in CALLING_CONVENTIONS:
                diag.add_error("FSPEC-CCONV-NONFUNC", f"Convencion de llamada '{s}' no permitida en {ctx}", s)


class TypeSpecifierHandler:
    # Validador de la composicion de especificadores de tipo fundamental

    ALLOWED_INTEGERS = {
        ("char",), ("signed", "char"), ("unsigned", "char"),
        ("short",), ("signed", "short"), ("short", "int"), ("signed", "short", "int"),
        ("unsigned", "short"), ("unsigned", "short", "int"),
        ("int",), ("signed",), ("signed", "int"), ("unsigned",), ("unsigned", "int"),
        ("long",), ("signed", "long"), ("long", "int"), ("signed", "long", "int"),
        ("unsigned", "long"), ("unsigned", "long", "int"),
        ("long long",), ("signed", "long long"), ("long long", "int"), ("signed", "long long", "int"),
        ("unsigned", "long long"), ("unsigned", "long long", "int"),
        ("bool",), ("_Bool",),
    }

    ALLOWED_FLOATS = {
        ("float",), ("double",), ("long", "double"),
        ("float", "_Complex"), ("double", "_Complex"), ("long", "double", "_Complex"),
        ("float", "_Imaginary"), ("double", "_Imaginary"), ("long", "double", "_Imaginary"),
        ("_Decimal32",), ("_Decimal64",), ("_Decimal128",),
    }

    @classmethod
    def validate_basic_type_composition(cls, tokens: list[str], diag: SemanticDiagnostics, ctx: str = "tipo") -> str:
        # Valida combinaciones validas de tipos primitivos de C (ej: unsigned long long int)
        cleaned = [t for t in tokens if t not in ("const", "volatile", "restrict", "_Atomic")]
        if not cleaned:
            diag.add_error("TYPE-EMPTY", f"Especificador de tipo ausente en {ctx}")
            return "int"

        # Filtrar void
        if "void" in cleaned:
            if len(cleaned) > 1:
                diag.add_error("TYPE-VOID-COMBO", f"'void' no puede combinarse con otros tipos en {ctx}: {' '.join(cleaned)}")
            return "void"

        # Orden canonico para matching
        words = tuple(cleaned)
        if words in cls.ALLOWED_INTEGERS:
            return " ".join(words)
        if words in cls.ALLOWED_FLOATS:
            return " ".join(words)

        # Chequeos especificos de errores comunes
        signed_count = sum(1 for w in cleaned if w in ("signed", "__signed", "__signed__"))
        unsigned_count = sum(1 for w in cleaned if w == "unsigned")
        if signed_count > 0 and unsigned_count > 0:
            diag.add_error("TYPE-SIGNED-UNSIGNED", f"Combinacion imposible de 'signed' y 'unsigned' en {ctx}")

        long_count = sum(1 for w in cleaned if w == "long") + (2 if "long long" in cleaned else 0)
        if long_count > 2:
            diag.add_error("TYPE-LONG-OVERFLOW", f"Demasiados especificadores 'long' ({long_count}) en {ctx}")

        short_count = sum(1 for w in cleaned if w == "short")
        if short_count > 0 and long_count > 0:
            diag.add_error("TYPE-SHORT-LONG", f"'short' y 'long' no pueden combinarse en {ctx}")

        if short_count > 0 and any(f in cleaned for f in ("float", "double")):
            diag.add_error("TYPE-SHORT-FLOAT", f"'short' no puede combinarse con tipos de punto flotante en {ctx}")

        if long_count > 0 and "float" in cleaned:
            diag.add_error("TYPE-LONG-FLOAT", f"'long float' es una combinacion invalida en C estandar en {ctx}")

        return " ".join(cleaned)


def get_node_children(node: Any) -> list[Any]:
    # Obtiene la lista de nodos hijos considerando listas, tuplas y tipos de nodo de Gram
    if isinstance(node, (list, tuple)):
        return list(node)
    if isinstance(node, gast.ASTRef):
        return node.nodes
    if isinstance(node, gast.ArrayNode):
        return list(node.items)
    return []


def extract_ast_tokens(node: Any) -> list[TokenType]:
    # Extrae recursivamente todos los tokens reales desde el AST
    results: list[TokenType] = []
    if isinstance(node, (list, tuple)):
        for item in node:
            results.extend(extract_ast_tokens(item))
        return results

    if isinstance(node, gast.ASTTokenNode):
        return [node.token]

    for child in get_node_children(node):
        results.extend(extract_ast_tokens(child))
    return results


def find_ast_nodes(node: Any, target_name: str) -> list[gast.ASTRef]:
    # Busca recursivamente todos los nodos ASTRef con un nombre determinado
    results: list[gast.ASTRef] = []
    if isinstance(node, (list, tuple)):
        for item in node:
            results.extend(find_ast_nodes(item, target_name))
        return results

    if isinstance(node, gast.ASTRef) and node.name == target_name:
        results.append(node)

    for child in get_node_children(node):
        results.extend(find_ast_nodes(child, target_name))
    return results


__all__ = [
    'CALLING_CONVENTIONS',
    'FunctionSpecifierHandler',
    'IssueSeverity',
    'NORM_FUNC_SPECS',
    'NORM_QUALIFIERS',
    'QualifierHandler',
    'STORAGE_CLASSES',
    'SemanticDiagnostics',
    'SemanticIssue',
    'StorageSpecifierHandler',
    'TypeSpecifierHandler',
    'extract_ast_tokens',
    'find_ast_nodes',
    'get_node_children',
]

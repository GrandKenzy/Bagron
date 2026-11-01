"""Puente entre el árbol GIR de Gram AOT y el AST Python de Bagron."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any

from gram.core.ast.nodes import (
    ASTKeyword,
    ASTNode,
    ASTRef,
    ASTTokenNode,
    ArrayNode,
    Identifier,
    LiteralNumber,
    LiteralString,
    LiteralSymbol,
    RawNode,
)
from gram.core.combinators.expressions import ASTBinaryOp, ASTUnaryOp
from gram.core.lexer.tokens import Token, TokenType
from gram.ir import GirView


class AotAstError(ValueError):
    """Indica que un árbol GIR no puede conservar la forma del AST de Gram."""


class AotParserError(RuntimeError):
    """Indica que el parser C no pudo producir un GIR válido."""


class AotParserUnavailable(AotParserError):
    """Indica que no hay un ejecutable AOT configurado o disponible."""


class AotParser:
    """Invoca el parser C exportado por Gram y reconstruye el AST de Bagron."""

    def __init__(self, executable: str | Path, *, timeout: float = 60.0):
        path = Path(executable).expanduser()
        if not path.is_file():
            raise AotParserUnavailable(
                f'No se encontró el parser AOT de Gram: {path}'
            )
        self.executable = path.resolve()
        self.timeout = timeout

    @classmethod
    def from_config(
        cls,
        executable: str | Path | None = None,
        *,
        timeout: float = 60.0,
    ) -> 'AotParser':
        configured = executable or os.environ.get('BAGRON_AOT_PARSER')
        if not configured:
            repository_root = Path(__file__).resolve().parents[2]
            for candidate in (
                repository_root / 'build' / 'aot' / 'bagron_aot.exe',
                repository_root / 'build' / 'aot' / 'bagron_aot',
            ):
                if candidate.is_file():
                    configured = candidate
                    break
        if not configured:
            raise AotParserUnavailable(
                'No hay parser AOT configurado; usa tools/build_aot_parser.py, '
                '--aot-parser o BAGRON_AOT_PARSER.'
            )
        return cls(os.path.expandvars(str(configured)), timeout=timeout)

    def parse(
        self,
        source: str | bytes | Iterable[str],
        *,
        session: Any,
        name: str = '<aot>',
    ) -> list[ASTNode]:
        """Analiza `source` mediante GIR y devuelve raíces compatibles con Bagron."""
        source_bytes = _source_bytes(source)
        source_name = Path(name).name or 'source.bg'
        if not Path(source_name).suffix:
            source_name += '.bg'

        with tempfile.TemporaryDirectory(prefix='bagron-aot-') as directory:
            directory_path = Path(directory)
            source_path = directory_path / source_name
            gir_path = directory_path / f'{source_path.stem}.gir'
            source_path.write_bytes(source_bytes)
            try:
                result = subprocess.run(
                    [
                        str(self.executable),
                        'compile',
                        str(source_path),
                        '-o',
                        str(gir_path),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=self.timeout,
                )
            except OSError as error:
                raise AotParserError(
                    f'No se pudo ejecutar el parser AOT {self.executable}: {error}'
                ) from error
            except subprocess.TimeoutExpired as error:
                raise AotParserError(
                    f'El parser AOT excedió el tiempo límite de {self.timeout:g} s.'
                ) from error

            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                raise AotParserError(
                    f'El parser AOT rechazó {name}'
                    + (f': {detail}' if detail else '.')
                )
            if not gir_path.is_file():
                raise AotParserError(
                    f'El parser AOT terminó correctamente pero no produjo GIR para {name}.'
                )

            try:
                source_view = GirView.from_file(
                    gir_path,
                    source=source_bytes,
                    session=session,
                )
                return ast_from_gir(
                    source_view,
                    source_bytes,
                    session=session,
                    name=name,
                )
            except (AotAstError, ValueError) as error:
                raise AotParserError(
                    f'El GIR producido para {name} no coincide con Bagron: {error}'
                ) from error


def _source_bytes(source: str | bytes | Iterable[str]) -> bytes:
    if isinstance(source, bytes):
        return source
    if isinstance(source, str):
        return source.encode('utf-8')
    return ''.join(source).encode('utf-8')


# `Separator` es el único combinador de Bagron que devuelve ArrayNode. Las
# secuencias y repeticiones restantes devuelven listas que Gram aplana al
# incorporarlas a la regla padre; el generador C representa ambas como ARRAY.
_SEPARATOR_ARRAY_PARENTS = frozenset(
    {'IMPORT_GROUP', 'PARAMETERS', 'ARGUMENTS', 'ARRAY_VALUE'}
)
_ROOT_REPETITION_RULES = frozenset(
    {'DECORATORS', 'POINTER', 'AGGREGATE_DECORATORS'}
)


def ast_from_gir(
    view: GirView,
    source: str | bytes | Iterable[str],
    *,
    session: Any,
    name: str = '<aot>',
) -> list[ASTNode]:
    """Convierte la raíz GIR en la lista de nodos que devuelve Gram Python.

    `source` debe ser exactamente el texto usado para producir el GIR,
    conservando sus saltos de línea. Los spans GIR son offsets UTF-8; se
    valida su tamaño antes de reutilizar los tokens de la sesión Python.
    """
    source_bytes = _source_bytes(source)
    if view.header.source_size != len(source_bytes):
        raise AotAstError(
            'El GIR y la fuente no coinciden en tamaño; conserva los saltos '
            'de línea originales al cargar el archivo.'
        )

    source_text = source_bytes.decode('utf-8')
    tokens = tuple(session.tokenize(source_text, name))
    tokens_by_position: defaultdict[tuple[int, int], list[TokenType]] = defaultdict(list)
    tokens_by_kind: defaultdict[Token, list[TokenType]] = defaultdict(list)
    token_offsets: dict[int, int] = {}
    for token in tokens:
        position = (token.line, token.col)
        tokens_by_position[position].append(token)
        if isinstance(token.token, Token):
            tokens_by_kind[token.token].append(token)
        token_offsets[id(token)] = _source_offset(source_bytes, token.line, token.col)

    def convert(node: Any, parent_name: str | None = None) -> ASTNode | list[ASTNode]:
        if node.is_terminal:
            return _terminal(node, tokens_by_position)

        if node.is_raw:
            return RawNode(node.tokens, node.text)

        if node.is_expr:
            children = _flatten(convert(child, node.kind_name) for child in node.children)
            operator = _expression_operator(node, token_offsets, tokens_by_kind)
            if node.kind_name == 'EXPR_UNARY':
                if len(children) != 1:
                    raise AotAstError('EXPR_UNARY no contiene exactamente un operando.')
                return ASTUnaryOp(operator, children[0])
            if node.kind_name == 'EXPR_BINARY':
                if len(children) != 2:
                    raise AotAstError('EXPR_BINARY no contiene exactamente dos operandos.')
                return ASTBinaryOp(children[0], operator, children[1])
            raise AotAstError(f'Clase de expresión AOT desconocida: {node.kind_name}')

        if node.is_array:
            values = [convert(child, parent_name) for child in node.children]
            if parent_name in _SEPARATOR_ARRAY_PARENTS:
                return ArrayNode(values)
            return values

        children = [convert(child, node.kind_name) for child in node.children]
        children = _group_transparent_type(node.kind_name, children)
        if node.kind_name in _ROOT_REPETITION_RULES:
            children = _flatten(children)
        if node.kind_name == 'ENTRYPOINT':
            return _flatten(children)
        return ASTRef(node.kind_name, children)

    result = convert(view.root)
    return result if isinstance(result, list) else [result]


def _flatten(values: Iterable[ASTNode | list[ASTNode]]) -> list[ASTNode]:
    result: list[ASTNode] = []
    for value in values:
        if isinstance(value, list):
            result.extend(value)
        else:
            result.append(value)
    return result


def _group_transparent_type(rule_name: str, children: list[Any]) -> list[Any]:
    """Restore the list returned by Bagron's transparent `TYPE` rule."""
    if rule_name not in {
        'VAR_DECLARATION',
        'VAR_INITIALIZATION',
        'FUNCTION_SIGNATURE',
        'PAIR_PARAM',
        'FLAGS_SIGNATURE',
        'EXTERN_RETURN',
        'ENUM',
        'FOR_SIGNATURE',
    }:
        return children

    if rule_name in {'VAR_DECLARATION', 'VAR_INITIALIZATION', 'PAIR_PARAM'}:
        start = _after_token(children, 'COLON')
        if start is None:
            return children
        children = _lift_nested_boundary(children, start, 'ASSIGN')
        end = _before_token(children, 'ASSIGN', start)
        if end is None:
            end = len(children)
        return _replace_range(children, start, end, wrap_type_suffixes=True)

    if rule_name == 'FUNCTION_SIGNATURE':
        start = _after_rule(children, 'PARAMETERS')
        if start is None:
            return children
        end = _first_index(children, {'POINTER', 'COLON'}, start)
        if end is None:
            return children
        return _replace_range(children, start, end, wrap_type_suffixes=True)

    if rule_name == 'FLAGS_SIGNATURE':
        start = _after_token(children, 'IDENT')
        end = _first_index(children, {'COLON'}, start or 0)
        if start is None or end is None:
            return children
        return _replace_range(children, start, end, wrap_type_suffixes=True)

    if rule_name == 'ENUM':
        start = _after_token(children, 'IDENT')
        end = _first_index(children, {'COLON'}, start or 0)
        if start is None or end is None:
            return children
        return _replace_range(children, start, end, wrap_type_suffixes=True)

    if rule_name == 'FOR_SIGNATURE':
        start = _after_token(children, 'COLON')
        end = _first_keyword(children, {'ran', 'in'}, start or 0)
        if start is None or end is None:
            return children
        return _replace_range(children, start, end, wrap_type_suffixes=True)

    # EXTERN_RETURN has an optional [POINTER, COLON] sequence, then TYPE.
    colon_index = _first_index(children, {'COLON'}, 0)
    if colon_index is not None:
        return _replace_range(children, colon_index + 1, len(children), wrap_type_suffixes=True)
    nested_colon = next(
        (
            index
            for index, child in enumerate(children)
            if isinstance(child, list) and _contains_token(child, 'COLON')
        ),
        None,
    )
    if nested_colon is not None:
        return _replace_range(children, nested_colon + 1, len(children), wrap_type_suffixes=True)
    return _replace_range(children, 0, len(children), wrap_type_suffixes=True)


def _replace_range(
    children: list[Any],
    start: int,
    end: int,
    *,
    wrap_type_suffixes: bool = False,
) -> list[Any]:
    grouped = children[start:end]
    if wrap_type_suffixes:
        grouped = [_restore_type_child(child) for child in grouped]
    return [*children[:start], grouped, *children[end:]]


def _restore_type_child(child: Any) -> Any:
    """Restore one suffix per nested list after GIR splices `ARRAY_SUFFIX`."""
    if not isinstance(child, list) or not child:
        return child
    if all(isinstance(item, list) for item in child):
        return child

    suffixes: list[list[Any]] = []
    current: list[Any] | None = None
    for item in child:
        if _token_name(item) == 'LBRACKET':
            if current is not None:
                return child
            current = [item]
            continue
        if current is None:
            return child
        current.append(item)
        if _token_name(item) == 'RBRACKET':
            suffixes.append(current)
            current = None

    if current is not None or not suffixes:
        return child
    return suffixes


def _lift_nested_boundary(
    children: list[Any],
    start: int,
    token_name: str,
) -> list[Any]:
    """Lift an optional tail spliced inside a transparent GIR rule.

    A transparent `TYPE` followed by `Opt(Seq(ASSIGN, VALUE))` can arrive as
    `[TYPE_PARTS, [ASSIGN, VALUE]]` in GIR. Python Gram keeps that optional
    sequence as a sibling of the type, so restore the sibling boundary before
    grouping `TYPE`.
    """
    for index in range(start, len(children)):
        child = children[index]
        if not isinstance(child, list):
            continue
        for nested_index, nested in enumerate(child):
            if not isinstance(nested, list) or not nested:
                continue
            if _token_name(nested[0]) != token_name:
                continue
            prefix = child[:nested_index]
            return [
                *children[:index],
                prefix,
                *children[index + 1:],
                nested,
            ]
    return children


def _token_name(value: Any) -> str | None:
    if not isinstance(value, ASTTokenNode):
        return None
    return getattr(value.token.token, 'name', None)


def _after_token(children: list[Any], token_name: str, start: int = 0) -> int | None:
    index = _first_index(children, {token_name}, start)
    return None if index is None else index + 1


def _before_token(children: list[Any], token_name: str, start: int) -> int | None:
    return _first_index(children, {token_name}, start)


def _after_rule(children: list[Any], rule_name: str, start: int = 0) -> int | None:
    index = next(
        (i for i, child in enumerate(children[start:], start) if isinstance(child, ASTRef) and child.name == rule_name),
        None,
    )
    return None if index is None else index + 1


def _first_index(children: list[Any], names: set[str], start: int) -> int | None:
    for index in range(start, len(children)):
        child = children[index]
        if isinstance(child, ASTRef) and child.name in names:
            return index
        if isinstance(child, ASTTokenNode) and getattr(child.token.token, 'name', None) in names:
            return index
        if isinstance(child, list) and child and _token_name(child[0]) in names:
            return index
    return None


def _first_keyword(children: list[Any], values: set[str], start: int) -> int | None:
    for index in range(start, len(children)):
        child = children[index]
        if (
            isinstance(child, ASTTokenNode)
            and child.token.token == Token.KEYWORD
            and str(child.token.value) in values
        ):
            return index
    return None


def _contains_token(value: Any, token_name: str) -> bool:
    if isinstance(value, ASTTokenNode):
        return getattr(value.token.token, 'name', None) == token_name
    if isinstance(value, list):
        return any(_contains_token(item, token_name) for item in value)
    return False


def _terminal(
    node: Any,
    tokens_by_position: dict[tuple[int, int], list[TokenType]],
) -> ASTTokenNode:
    expected = Token.from_string(node.kind_name)
    candidates = tokens_by_position.get((node.line, node.column), [])
    token = next((candidate for candidate in candidates if candidate.token == expected), None)
    if token is None:
        actual = getattr(candidates[0].token, 'name', candidates[0].token) if candidates else 'ausente'
        raise AotAstError(
            f'El token AOT {node.kind_name} no coincide con el token Python '
            f'{actual} en {node.line}:{node.column}.'
        )

    if token.token == Token.KEYWORD:
        return ASTKeyword(token)
    if token.token == Token.IDENT:
        return Identifier(token)
    if token.token in (Token.NUMBER, Token.DECIMAL):
        return LiteralNumber(token)
    if token.token == Token.STRING:
        return LiteralString(token)
    return LiteralSymbol(token)


def _expression_operator(
    node: Any,
    token_offsets: dict[int, int],
    tokens_by_kind: dict[Token, list[TokenType]],
) -> TokenType:
    operator = Token.from_code(node.value)
    if operator is None:
        raise AotAstError(f'Operador AOT desconocido: {node.value}.')

    start = node.src_start
    end = start + node.src_length
    candidates = [
        token for token in tokens_by_kind.get(operator, ())
        if start <= token_offsets[id(token)] < end
    ]
    if not candidates:
        raise AotAstError(
            f'No se encontró el operador {operator.name} dentro del span de expresión.'
        )
    return candidates[0]


def _source_offset(source: bytes, line: int, column: int) -> int:
    if line < 1:
        return column
    lines = source.splitlines(keepends=True)
    if line > len(lines):
        return len(source)
    prefix = b''.join(lines[:line - 1])
    line_text = lines[line - 1].decode('utf-8', errors='replace')
    return len(prefix) + len(line_text[:column].encode('utf-8'))


__all__ = [
    'AotAstError',
    'AotParser',
    'AotParserError',
    'AotParserUnavailable',
    'ast_from_gir',
]

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path

from core.frontend.objects import AggregateSymbol, DefinedIntegerSymbol
from core.frontend.syntax.keywords import INTRINSIC_TYPES
from core.frontend.tools.types import (
    TypeResolutionError,
    register_defined_integer_name,
)


_DIRECTIVE = re.compile(
    r'^\s*#(?P<kind>defint|defuint)\s+'
    r'(?P<width>[0-9]+)\s*,\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*$'
)


@dataclass(frozen=True)
class IntegerDirective:
    kind: str
    width: int
    name: str
    line: int


def _validate_width(width: int) -> None:
    if width < 1:
        raise TypeResolutionError(
            f'El ancho de un entero definido debe ser mayor que cero: {width}'
        )
    try:
        from llvmlite import ir
        ir.IntType(width)
    except (ImportError, ValueError, TypeError) as error:
        raise TypeResolutionError(
            f'LLVM no puede procesar un entero de {width} bits: {error}'
        ) from error


def extract_integer_directives(
    content: str | list[str],
    source: Path,
) -> tuple[str | list[str], tuple[IntegerDirective, ...], tuple[str, ...]]:
    """Remove active integer directives while preserving source line numbers."""
    was_list = isinstance(content, list)
    lines = list(content) if was_list else content.splitlines(keepends=True)
    directives: list[IntegerDirective] = []
    errors: list[str] = []
    output: list[str] = []
    for line_number, line in enumerate(lines, 1):
        raw = line.rstrip('\r\n')
        if not raw.lstrip().startswith(('#defint', '#defuint')):
            output.append(line)
            continue
        match = _DIRECTIVE.fullmatch(raw)
        if match is None:
            errors.append(
                f'{source}:{line_number}: directiva invalida; usa '
                '#defint <ancho>, <nombre> o #defuint <ancho>, <nombre>'
            )
            output.append('\n' if line.endswith('\n') else '')
            continue
        kind = match.group('kind')
        width = int(match.group('width'))
        name = match.group('name')
        try:
            _validate_width(width)
        except TypeResolutionError as error:
            errors.append(f'{source}:{line_number}: {error}')
        if name in INTRINSIC_TYPES or name in {'Bint', 'fields', 'struct', 'mold'}:
            errors.append(
                f'{source}:{line_number}: el nombre de tipo {name} esta reservado'
            )
        directives.append(IntegerDirective(kind, width, name, line_number))
        output.append('\n' if line.endswith('\n') else '')
    return (output if was_list else ''.join(output)), tuple(directives), tuple(errors)


def register_integer_directives(
    compiler: object,
    source: Path,
    directives: tuple[IntegerDirective, ...],
) -> None:
    storage = compiler.storage
    exported = compiler.integer_directives_by_module.setdefault(
        source.resolve(), set()
    )
    for directive in directives:
        if any(
            isinstance(existing, AggregateSymbol)
            and existing.kind == 'fields'
            for existing in storage.type_candidates.get(directive.name, ())
        ):
            compiler.error(
                f'{source}:{directive.line}: el entero definido '
                f'{directive.name} colisiona con fields del mismo nombre'
            )
            continue
        symbol = DefinedIntegerSymbol(
            name=directive.name,
            bit_width=directive.width,
            signed=directive.kind == 'defint',
            module_path=source.resolve(),
        )
        if not storage.define_type(symbol):
            compiler.error(
                f'{source}:{directive.line}: el tipo ya fue declarado: '
                f'{directive.name}'
            )
            continue
        register_defined_integer_name(
            directive.name,
            directive.width,
            directive.kind == 'defint',
        )
        exported.add(directive.name)


__all__ = [
    'IntegerDirective',
    'extract_integer_directives',
    'register_integer_directives',
]

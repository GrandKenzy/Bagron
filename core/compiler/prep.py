from __future__ import annotations

import re
import textwrap
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class PrepBlock:
    """One raw assembler block extracted before Bagron tokenization."""

    source: Path
    function_name: str | None
    dialect: str
    body: str
    line: int
    is_module: bool = False


class PrepError(ValueError):
    """Raised when a prep template cannot be lowered for the selected target."""


@dataclass
class _ActivePrep:
    body: list[str]
    dialect: str
    function_name: str | None
    line: int
    valid: bool
    is_module: bool = False


_PREP_RE = re.compile(
    r'^(?P<indent>[ \t]*)#prep[ \t]+assembler[ \t]+'
    r'(?P<quote>["\'])(?P<dialect>.*?)\2[ \t]*$'
)
_MODULE_PREP_RE = re.compile(
    r'^(?P<indent>[ \t]*)#prep[ \t]+assembler[ \t]+module[ \t]+'
    r'(?P<quote>["\'])(?P<dialect>.*?)\2[ \t]*$'
)
_FUNCTION_RE = re.compile(
    r'^(?P<indent>[ \t]*)(?:(?:public|private)[ \t]+)?'
    r'(?:(?:inline)[ \t]+)?func[ \t]+'
    r'(?P<name>[A-Za-z_]\w*)\b.*:[ \t]*$'
)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(' \t'))


def _blank_line(line: str) -> str:
    return '\n' if line.endswith(('\n', '\r')) else ''


def extract_prep_blocks(
    lines: Sequence[str],
    source: Path,
) -> tuple[list[str], list[PrepBlock], list[str]]:
    """Remove raw prep blocks and return parser-safe lines plus diagnostics."""
    transformed: list[str] = []
    blocks: list[PrepBlock] = []
    errors: list[str] = []
    function_stack: list[tuple[int, str]] = []
    active: _ActivePrep | None = None
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        indent = _indent(line)

        if active is not None:
            if stripped == '#end':
                if active.valid:
                    body = textwrap.dedent(''.join(active.body))
                    blocks.append(
                        PrepBlock(
                            source=source,
                            function_name=active.function_name,
                            dialect=active.dialect,
                            body=body,
                            line=active.line,
                            is_module=active.is_module,
                        )
                    )
                transformed.append(_blank_line(line))
                active = None
                index += 1
                continue

            active.body.append(line)
            transformed.append(_blank_line(line))
            index += 1
            continue

        function_match = _FUNCTION_RE.match(line.rstrip('\r\n'))
        if function_match is not None:
            function_indent = len(function_match.group('indent'))
            while function_stack and function_indent <= function_stack[-1][0]:
                function_stack.pop()
            function_stack.append((function_indent, function_match.group('name')))
            transformed.append(line)
            index += 1
            continue

        while function_stack and indent <= function_stack[-1][0] and stripped:
            function_stack.pop()

        if stripped == '#end':
            errors.append(f'{source}:{index + 1}: #end no tiene un #prep abierto')
            transformed.append(_blank_line(line))
            index += 1
            continue

        if stripped.startswith('#prep'):
            module_match = _MODULE_PREP_RE.match(line.rstrip('\r\n'))
            if module_match is not None:
                if function_stack:
                    errors.append(
                        f'{source}:{index + 1}: #prep assembler module solo '
                        'se permite a nivel de modulo'
                    )
                    transformed.append(_blank_line(line))
                    active = _ActivePrep(
                        [], module_match.group('dialect'), None,
                        index + 1, False, True,
                    )
                    index += 1
                    continue

                transformed.append(_blank_line(line))
                active = _ActivePrep(
                    [], module_match.group('dialect'), None,
                    index + 1, True, True,
                )
                index += 1
                continue

            match = _PREP_RE.match(line.rstrip('\r\n'))
            if match is None:
                errors.append(
                    f'{source}:{index + 1}: se esperaba '
                    '#prep assembler "dialecto"'
                )
                transformed.append(_blank_line(line))
                active = _ActivePrep([], '', None, index + 1, False)
                index += 1
                continue

            if not function_stack or indent <= function_stack[-1][0]:
                errors.append(
                    f'{source}:{index + 1}: #prep solo se permite dentro de una funcion'
                )
                transformed.append(_blank_line(line))
                active = _ActivePrep(
                    [], match.group('dialect'), None, index + 1, False
                )
                index += 1
                continue

            transformed.append(f'{match.group("indent")}pass\n')
            active = _ActivePrep(
                [], match.group('dialect'), function_stack[-1][1], index + 1, True
            )
            index += 1
            continue

        transformed.append(line)
        index += 1

    if active is not None:
        errors.append(
            f'{source}:{active.line}: #prep no tiene un #end de cierre'
        )

    return transformed, blocks, errors


def _safe_component(value: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', value) or '_'


def _windows_x64_registers(target_triple: str) -> tuple[dict[str, str], ...]:
    normalized = target_triple.lower()
    if not normalized.startswith(('x86_64-', 'amd64-')) or 'windows' not in normalized:
        raise PrepError(
            'Las funciones @assembler requieren el target Windows x64 en esta fase'
        )
    return (
        {'full': 'rcx', 'dword': 'ecx', 'word': 'cx', 'byte': 'cl'},
        {'full': 'rdx', 'dword': 'edx', 'word': 'dx', 'byte': 'dl'},
        {'full': 'r8', 'dword': 'r8d', 'word': 'r8w', 'byte': 'r8b'},
        {'full': 'r9', 'dword': 'r9d', 'word': 'r9w', 'byte': 'r9b'},
    )


def _normalize_dialect(dialect: str) -> str:
    normalized = dialect.strip().lower()
    if normalized in {'gas-intel', 'gas_intel', 'intel-gas', 'intel'}:
        # ``intel`` remains a compatibility alias. The emitted syntax is
        # GAS/LLVM Intel syntax, not NASM syntax.
        return 'gas-intel'
    if normalized in {'att', 'at&t', 'att_syntax'}:
        return 'att'
    if normalized in {'nasm', 'intel-nasm'}:
        raise PrepError(
            'El dialecto NASM no es compatible con el ensamblador integrado de '
            'Clang; usa "gas-intel" para Intel-GAS o configura un backend NASM'
        )
    raise PrepError(
        f'Dialecto ASM no soportado en esta fase: {dialect!r}; '
        'usa "gas-intel" o "att"'
    )


def _parameter_width(parameter: object) -> int:
    type_spec = getattr(parameter, 'type_spec', None)
    if type_spec is None:
        raise PrepError('Los parametros de @assembler deben tener un tipo')
    if getattr(type_spec, 'array_depth', 0):
        raise PrepError(
            'Los parametros de @assembler no pueden ser arrays'
        )
    if getattr(type_spec, 'pointer_level', 0):
        # Windows x64 passes every pointer-sized argument through the integer
        # register/stack classes.  Templates may therefore refer to a pointer
        # parameter with {name}; the width aliases resolve to RCX/RDX/R8/R9
        # (or their AT&T spellings) just like a 64-bit integer.
        return 64

    name = getattr(type_spec, 'name', None)
    if name in {'Bint', 'uBint', 'usize', 'isize'}:
        width = getattr(type_spec, 'bit_width', None)
    else:
        width = {
            'bool': 1,
            'char': 8,
            'byte': 8,
            'int8': 8,
            'uint8': 8,
            'int16': 16,
            'uint16': 16,
            'int32': 32,
            'uint32': 32,
            'int64': 64,
            'uint64': 64,
        }.get(name)
    if width is None or width < 1 or width > 64:
        raise PrepError(
            f'El tipo {getattr(type_spec, "canonical_name", name)!r} '
            'no tiene un ancho entero compatible con Windows x64'
        )
    return int(width)


def _register_for_width(register: dict[str, str], width: int) -> str:
    if width <= 8:
        return register['byte']
    if width <= 16:
        return register['word']
    if width <= 32:
        return register['dword']
    return register['full']


def _stack_operand(index: int, dialect: str) -> str:
    # At function entry, Windows x64 places the fifth argument after the
    # return address and the 32-byte shadow space: rsp + 0x28.
    offset = 0x28 + (index - 4) * 8
    if dialect == 'gas-intel':
        return f'[rsp + 0x{offset:x}]'
    return f'{offset}(%rsp)'


def _expand_template(
    body: str,
    parameters: Sequence[object],
    target_triple: str,
    dialect: str,
) -> str:
    registers = _windows_x64_registers(target_triple)
    bindings: dict[str, str] = {}
    for index, parameter in enumerate(parameters):
        name = str(getattr(parameter, 'name', ''))
        width = _parameter_width(parameter)
        if index < len(registers):
            value = _register_for_width(registers[index], width)
            if dialect == 'att':
                value = f'%{value}'
        else:
            value = _stack_operand(index, dialect)
        bindings[name] = value
    if any(not name for name in bindings):
        raise PrepError('Todos los parametros de @assembler deben tener nombre')

    output: list[str] = []
    index = 0
    while index < len(body):
        if body.startswith('{{', index):
            output.append('{')
            index += 2
            continue
        if body.startswith('}}', index):
            output.append('}')
            index += 2
            continue
        if body[index] == '{':
            end = body.find('}', index + 1)
            if end < 0:
                raise PrepError('La plantilla ASM contiene una llave sin cerrar')
            name = body[index + 1:end]
            if not re.fullmatch(r'[A-Za-z_]\w*', name):
                raise PrepError(f'Placeholder ASM invalido: {{{name}}}')
            if name not in bindings:
                raise PrepError(
                    f'El parametro ASM no existe en la firma: {name}'
                )
            output.append(bindings[name])
            index = end + 1
            continue
        if body[index] == '}':
            raise PrepError('La plantilla ASM contiene una llave sin abrir')
        output.append(body[index])
        index += 1

    return ''.join(output)


def _render_assembly(
    block: PrepBlock,
    function: object,
    target_triple: str,
) -> str:
    dialect = _normalize_dialect(block.dialect)

    signature = getattr(function, 'signature', None)
    parameters = getattr(signature, 'parameters', ())
    body = _expand_template(block.body, parameters, target_triple, dialect)
    if any(re.match(r'^\s*ret(?:q)?(?:\s|$)', line, re.IGNORECASE)
           for line in body.splitlines()):
        raise PrepError(
            'El bloque ASM no debe contener ret; return asm agrega el retorno ABI'
        )

    symbol_name = '__bagron_main' if block.function_name == 'main' else block.function_name
    syntax = '.intel_syntax noprefix' if dialect == 'gas-intel' else '.att_syntax prefix'
    return_type = getattr(getattr(function, 'signature', None), 'return_type', None)
    is_void = (
        getattr(return_type, 'name', None) == 'void'
        and getattr(return_type, 'pointer_level', 0) == 0
        and getattr(return_type, 'array_depth', 0) == 0
    )
    status_setup = None if is_void else (
        'mov eax, 1' if dialect == 'gas-intel' else 'movl $1, %eax'
    )
    lines = [
        syntax,
        '.text',
        f'.globl {symbol_name}',
        f'{symbol_name}:',
    ]
    if status_setup is not None:
        lines.append(f'    {status_setup}')
    if body:
        lines.extend(
            f'    {line}' if line else ''
            for line in body.rstrip('\r\n').splitlines()
        )
    lines.extend(('    ret', ''))
    return '\n'.join(lines)


def _render_module_assembly(block: PrepBlock) -> str:
    """Render a module ASM unit without imposing a function ABI."""
    dialect = _normalize_dialect(block.dialect)
    if '{' in block.body or '}' in block.body:
        raise PrepError(
            'Un bloque ASM de modulo no admite placeholders de parametros; '
            'usa un bloque dentro de una funcion'
        )

    syntax = (
        '.intel_syntax noprefix'
        if dialect == 'gas-intel'
        else '.att_syntax prefix'
    )
    body = block.body.rstrip('\r\n')
    return f'{syntax}\n{body}\n' if body else f'{syntax}\n'


def write_prep_files(
    blocks: Sequence[PrepBlock],
    project_root: Path,
    build_root: Path | None = None,
    functions: Mapping[str, object] | None = None,
    target_triple: str | None = None,
) -> list[Path]:
    """Write extracted assembler blocks to unique `.asm` files."""
    root = build_root or project_root / 'build' / 'prep'
    counters: defaultdict[tuple[Path, str], int] = defaultdict(int)
    written: list[Path] = []
    cleaned_directories: set[Path] = set()

    if not blocks:
        if root.exists():
            for pattern in ('*__prep_*.asm', '*__prep_*.obj'):
                for previous in root.rglob(pattern):
                    previous.unlink()
        return written

    for block in blocks:
        source = block.source.resolve()
        try:
            relative = source.relative_to(project_root.resolve())
        except ValueError:
            relative = Path(source.name)

        module_parts = [
            _safe_component(part)
            for part in relative.with_suffix('').parts
        ]
        module_dir = root.joinpath(*module_parts)
        module_dir.mkdir(parents=True, exist_ok=True)
        if module_dir not in cleaned_directories:
            for pattern in ('*__prep_*.asm', '*__prep_*.obj'):
                for previous in module_dir.glob(pattern):
                    previous.unlink()
            cleaned_directories.add(module_dir)

        key = (source, block.function_name or '__module__')
        block_index = counters[key]
        counters[key] += 1
        function_name = _safe_component(block.function_name or 'module')
        destination = module_dir / f'{function_name}__prep_{block_index}.asm'
        function = functions.get(block.function_name) if functions is not None else None
        if block.is_module:
            content = _render_module_assembly(block)
        elif function is not None and target_triple is not None:
            content = _render_assembly(block, function, target_triple)
        else:
            content = block.body
        destination.write_text(content, encoding='utf-8')
        written.append(destination)

    return written


__all__ = [
    'PrepBlock',
    'PrepError',
    'extract_prep_blocks',
    'write_prep_files',
]

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, MutableMapping, Sequence


@dataclass(frozen=True)
class PrepBlock:
    """One raw assembler block extracted before Bagron tokenization."""

    source: Path
    function_name: str | None
    dialect: str
    body: str
    line: int


@dataclass(frozen=True)
class PrepBlockMetadata:
    """Map a generated assembly range back to one Bagron ASM block."""

    source: Path
    function_name: str | None
    dialect: str
    line: int
    generated_start: int
    generated_body_start: int
    generated_body_end: int
    generated_end: int


class PrepError(ValueError):
    """Raised when an assembler block cannot be lowered for the selected target."""


@dataclass
class _ActivePrep:
    body: list[str]
    dialect: str
    function_name: str | None
    line: int
    valid: bool


@dataclass
class _ConditionalBlock:
    """State for one conditional preprocessor block."""

    parent_active: bool
    branch_matched: bool
    active: bool
    else_seen: bool
    line: int


_ASSEMBLER_RE = re.compile(
    r'^(?P<indent>[ \t]*)#assembler[ \t]+'
    r'(?P<quote>["\'])(?P<dialect>.*?)\2[ \t]*$'
)
_FUNCTION_RE = re.compile(
    r'^(?P<indent>[ \t]*)(?:(?:public|private)[ \t]+)?'
    r'(?:(?:inline)[ \t]+)?func[ \t]+'
    r'(?P<name>[A-Za-z_]\w*)\b.*:[ \t]*$'
)
_LABEL_DEFINITION_RE = re.compile(
    r'^\s*(?P<label>[A-Za-z_.$][A-Za-z0-9_.$]*):(?:\s*.*)?$'
)
_CONDITIONAL_DIRECTIVE_RE = re.compile(
    r'^(?P<indent>[ \t]*)#(?P<directive>if|elif|else|end)\b(?P<rest>.*)$',
    re.IGNORECASE,
)
_CONDITION_RE = re.compile(
    r'^\s*(?P<flag>[A-Za-z_]\w*)\s*,\s*'
    r'(?P<quote>["\'])(?P<value>.*?)\2\s*$',
)
_PREPROCESSOR_ARCH_ALIASES = {
    'amd': 'x86_64',
    'amd64': 'x86_64',
    'x86_64': 'x86_64',
    'x86': 'i386',
    'i386': 'i386',
    'i686': 'i386',
    'arm': 'aarch64',
    'arm64': 'aarch64',
    'aarch64': 'aarch64',
    'riscv32': 'riscv32',
    'riscv64': 'riscv64',
}


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(' \t'))


def _blank_line(line: str) -> str:
    return '\n' if line.endswith(('\n', '\r')) else ''


def _normalize_preprocessor_architecture(value: str) -> str:
    normalized = str(value).strip().lower().split('-', 1)[0]
    return _PREPROCESSOR_ARCH_ALIASES.get(normalized, normalized)


def _parse_condition(
    expression: str,
) -> tuple[str, str] | None:
    match = _CONDITION_RE.fullmatch(expression)
    if match is None:
        return None

    flag = match.group('flag').upper()
    if flag not in {'OS', 'ARCH'}:
        return None
    return flag, match.group('value')


def _condition_matches(
    flag: str,
    value: str,
    system: str,
    architecture: str,
) -> bool:
    expected = value.strip().lower()
    if flag == 'OS':
        return expected == str(system).strip().lower()
    return _normalize_preprocessor_architecture(expected) == (
        _normalize_preprocessor_architecture(architecture)
    )


def _conditional_error(
    source: Path,
    line: int,
    message: str,
) -> str:
    return f'{source}:{line}: {message}'


def preprocess_conditionals(
    lines: Sequence[str],
    source: Path,
    *,
    system: str,
    architecture: str,
) -> tuple[list[str], list[str]]:
    """Select one non-nested conditional branch before Bagron tokenization.

    The supported form is ``#if OS, "windows"`` or ``#if ARCH, "amd"``;
    ``#elif``, ``#else`` and ``#end`` use the same block.  Inactive lines are
    replaced with blank lines so parser diagnostics retain source locations.
    """
    transformed: list[str] = []
    errors: list[str] = []
    stack: list[_ConditionalBlock] = []

    def is_active() -> bool:
        return all(block.active for block in stack)

    for index, line in enumerate(lines):
        raw_line = line.rstrip('\r\n')
        match = _CONDITIONAL_DIRECTIVE_RE.match(raw_line)
        if match is None:
            transformed.append(line if is_active() else _blank_line(line))
            continue

        directive = match.group('directive').lower()
        rest = match.group('rest').strip()
        source_line = index + 1

        if directive == 'if':
            if stack:
                errors.append(
                    _conditional_error(
                        source,
                        source_line,
                        'los bloques #if no se pueden anidar',
                    )
                )
            condition = _parse_condition(rest)
            if condition is None:
                errors.append(
                    _conditional_error(
                        source,
                        source_line,
                        '#if requiere OS o ARCH seguido de una cadena, por ejemplo '
                        '#if OS, "windows"',
                    )
                )
                flag, value = 'OS', ''
            else:
                flag, value = condition
            parent_active = is_active()
            matches = _condition_matches(flag, value, system, architecture)
            stack.append(
                _ConditionalBlock(
                    parent_active=parent_active,
                    branch_matched=matches,
                    active=parent_active and matches,
                    else_seen=False,
                    line=source_line,
                )
            )
            transformed.append(_blank_line(line))
            continue

        if directive == 'elif':
            if not stack:
                errors.append(
                    _conditional_error(
                        source,
                        source_line,
                        '#elif no tiene un #if abierto',
                    )
                )
                transformed.append(_blank_line(line))
                continue
            block = stack[-1]
            if block.else_seen:
                errors.append(
                    _conditional_error(
                        source,
                        source_line,
                        '#elif no puede aparecer despues de #else',
                    )
                )
                block.active = False
                transformed.append(_blank_line(line))
                continue
            condition = _parse_condition(rest)
            if condition is None:
                errors.append(
                    _conditional_error(
                        source,
                        source_line,
                        '#elif requiere OS o ARCH seguido de una cadena, por ejemplo '
                        '#elif ARCH, "amd"',
                    )
                )
                matches = False
            else:
                flag, value = condition
                matches = _condition_matches(flag, value, system, architecture)
            block.active = (
                block.parent_active
                and not block.branch_matched
                and matches
            )
            block.branch_matched = block.branch_matched or matches
            transformed.append(_blank_line(line))
            continue

        if directive == 'else':
            if not stack:
                errors.append(
                    _conditional_error(
                        source,
                        source_line,
                        '#else no tiene un #if abierto',
                    )
                )
                transformed.append(_blank_line(line))
                continue
            block = stack[-1]
            if rest:
                errors.append(
                    _conditional_error(
                        source,
                        source_line,
                        '#else no recibe una condicion',
                    )
                )
            if block.else_seen:
                errors.append(
                    _conditional_error(
                        source,
                        source_line,
                        'un bloque #if solo puede tener un #else',
                    )
                )
            block.else_seen = True
            block.active = block.parent_active and not block.branch_matched
            block.branch_matched = True
            transformed.append(_blank_line(line))
            continue

        if rest:
            errors.append(
                _conditional_error(
                    source,
                    source_line,
                    '#end no recibe argumentos',
                )
            )
        if not stack:
            # Existing conditional ``#end`` directives are handled here; an
            # assembler block terminator is consumed by ``extract_prep_blocks``.
            transformed.append(line)
            continue
        stack.pop()
        transformed.append(_blank_line(line))

    for block in stack:
        errors.append(
            _conditional_error(
                source,
                block.line,
                '#if no tiene un #end de cierre',
            )
        )

    return transformed, errors


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
            errors.append(f'{source}:{index + 1}: #end no tiene un bloque abierto')
            transformed.append(_blank_line(line))
            index += 1
            continue

        if stripped.startswith('#prep'):
            errors.append(
                f'{source}:{index + 1}: la directiva #prep fue retirada; '
                'usa #assembler "intel" o #assembler "att"'
            )
            transformed.append(_blank_line(line))
            active = _ActivePrep([], '', None, index + 1, False)
            index += 1
            continue

        if stripped.startswith('#assembler'):
            match = _ASSEMBLER_RE.match(line.rstrip('\r\n'))
            if match is None:
                errors.append(
                    f'{source}:{index + 1}: se esperaba '
                    '#assembler "intel" o #assembler "att" dentro de una funcion'
                )
                transformed.append(_blank_line(line))
                active = _ActivePrep([], '', None, index + 1, False)
                index += 1
                continue

            if not function_stack or indent <= function_stack[-1][0]:
                errors.append(
                    f'{source}:{index + 1}: #assembler solo se permite dentro de una funcion'
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
            f'{source}:{active.line}: #assembler no tiene un #end de cierre'
        )

    return transformed, blocks, errors


def _safe_component(value: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', value) or '_'


_WINDOWS_X64_REGISTERS: tuple[dict[str, str], ...] = (
    {'full': 'rcx', 'dword': 'ecx', 'word': 'cx', 'byte': 'cl'},
    {'full': 'rdx', 'dword': 'edx', 'word': 'dx', 'byte': 'dl'},
    {'full': 'r8', 'dword': 'r8d', 'word': 'r8w', 'byte': 'r8b'},
    {'full': 'r9', 'dword': 'r9d', 'word': 'r9w', 'byte': 'r9b'},
)

_SYSV_X64_REGISTERS: tuple[dict[str, str], ...] = (
    {'full': 'rdi', 'dword': 'edi', 'word': 'di', 'byte': 'dil'},
    {'full': 'rsi', 'dword': 'esi', 'word': 'si', 'byte': 'sil'},
    {'full': 'rdx', 'dword': 'edx', 'word': 'dx', 'byte': 'dl'},
    {'full': 'rcx', 'dword': 'ecx', 'word': 'cx', 'byte': 'cl'},
    {'full': 'r8', 'dword': 'r8d', 'word': 'r8w', 'byte': 'r8b'},
    {'full': 'r9', 'dword': 'r9d', 'word': 'r9w', 'byte': 'r9b'},
)


def _x64_abi_spec(
    target_triple: str,
    abi: str | None = None,
) -> tuple[tuple[dict[str, str], ...], int]:
    """Return the registered x86_64 ABI layout for a target."""
    normalized = target_triple.lower()
    if not normalized.startswith(('x86_64-', 'amd64-')):
        raise PrepError(
            'Las funciones @assembler requieren arquitectura x86_64 en esta fase'
        )
    if any(token in normalized for token in ('windows', 'win32', 'msvc', 'mingw')):
        # NOTA: Windows x64 ABI reserva 32 bytes de shadow space + 8 bytes de
        # direccion de retorno (0x28).
        return _WINDOWS_X64_REGISTERS, 0x28
    if any(token in normalized for token in ('linux', 'gnu', 'musl', 'freebsd')):
        # NOTA: System V AMD64 ABI pasa 6 registros y el 7.o argumento inicia
        # tras los 8 bytes de la direccion de retorno (0x08), sin shadow space.
        return _SYSV_X64_REGISTERS, 0x08
    if any(token in normalized for token in ('elf', 'none')):
        if str(abi or '').strip().lower() == 'sysv_amd64':
            # Baremetal selects System V explicitly; the LLVM C calling
            # convention for this AMD64 ELF target uses the same layout.
            return _SYSV_X64_REGISTERS, 0x08
        raise PrepError(
            'Las funciones @assembler de Baremetal requieren ABI "sysv_amd64"'
        )
    raise PrepError(
        f'Target ABI no soportado para @assembler: {target_triple!r}'
    )


def _windows_x64_registers(target_triple: str) -> tuple[dict[str, str], ...]:
    registers, _ = _x64_abi_spec(target_triple)
    return registers


def _normalize_dialect(dialect: str) -> str:
    normalized = dialect.strip().lower()
    if normalized == 'intel':
        return 'intel'
    if normalized == 'gas-intel':
        raise PrepError(
            'El dialecto "gas-intel" fue retirado; usa "intel" para la sintaxis Intel de GAS'
        )
    if normalized == 'att':
        return 'att'
    if normalized == 'nasm':
        raise PrepError(
            'El dialecto NASM no es compatible con el ensamblador integrado de '
            'Clang; usa "intel" para Intel-GAS o configura un backend NASM'
        )
    raise PrepError(
        f'Dialecto ASM no soportado en esta fase: {dialect!r}; '
        'usa "intel" o "att"'
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
        # register/stack classes.  The ABI validator therefore treats pointers
        # as 64-bit values for register and stack placement.
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
            'no tiene un ancho entero compatible con una ABI x86_64'
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


def _stack_operand(
    index: int,
    dialect: str,
    register_count: int = 4,
    stack_base: int = 0x28,
) -> str:
    offset = stack_base + (index - register_count) * 8
    if dialect == 'intel':
        return f'[rsp + 0x{offset:x}]'
    return f'{offset}(%rsp)'


def _validate_parameter_abi(
    parameters: Sequence[object],
    target_triple: str,
    dialect: str,
    abi: str | None = None,
) -> None:
    """Validate parameter widths and slots without rewriting ASM source."""
    registers, stack_base = _x64_abi_spec(target_triple, abi)
    for index, parameter in enumerate(parameters):
        width = _parameter_width(parameter)
        if index < len(registers):
            _register_for_width(registers[index], width)
        else:
            _stack_operand(index, dialect, len(registers), stack_base)


def _assembly_symbol_name(block: PrepBlock, function: object) -> str:
    return (
        '__bagron_main'
        if block.function_name == 'main'
        else getattr(function, 'llvm_name', None) or block.function_name
    )


def _render_assembly_lines(
    block: PrepBlock,
    function: object,
    target_triple: str,
    abi: str | None = None,
) -> tuple[list[str], int, int]:
    dialect = _normalize_dialect(block.dialect)

    signature = getattr(function, 'signature', None)
    parameters = getattr(signature, 'parameters', ())
    _validate_parameter_abi(parameters, target_triple, dialect, abi)
    body = block.body
    if any(re.match(r'^\s*ret(?:q)?(?:\s|$)', line, re.IGNORECASE)
           for line in body.splitlines()):
        raise PrepError(
            'El bloque ASM no debe contener ret; return asm agrega el retorno ABI'
        )

    symbol_name = _assembly_symbol_name(block, function)
    syntax = '.intel_syntax noprefix' if dialect == 'intel' else '.att_syntax prefix'
    return_type = getattr(getattr(function, 'signature', None), 'return_type', None)
    is_void = (
        getattr(return_type, 'name', None) == 'void'
        and getattr(return_type, 'pointer_level', 0) == 0
        and getattr(return_type, 'array_depth', 0) == 0
    )
    is_never = (
        getattr(return_type, 'name', None) == 'Never'
        and getattr(return_type, 'pointer_level', 0) == 0
        and getattr(return_type, 'array_depth', 0) == 0
    )
    # NOTA: Las funciones void y Never no retornan codigo de estado ABI.
    status_setup = None if (is_void or is_never) else (
        'mov eax, 1' if dialect == 'intel' else 'movl $1, %eax'
    )
    lines = [
        syntax,
        '.text',
        f'.globl {symbol_name}',
        f'{symbol_name}:',
    ]
    if status_setup is not None:
        lines.append(f'    {status_setup}')
    header_count = len(lines)
    body_lines = body.rstrip('\r\n').splitlines() if body else []
    lines.extend(f'    {line}' if line else '' for line in body_lines)
    # Never functions must not receive an implicit return. The ASM body is
    # responsible for guaranteeing that control never falls through into the
    # next symbol; void and value-returning functions keep their ABI return.
    if not is_never:
        lines.append('    ret')
    lines.append('')
    return lines, header_count, len(body_lines)


def _render_assembly(
    block: PrepBlock,
    function: object,
    target_triple: str,
    abi: str | None = None,
) -> str:
    """Render one block while preserving the legacy single-block API."""
    lines, _, _ = _render_assembly_lines(block, function, target_triple, abi)
    return '\n'.join(lines)


def _function_for_block(
    block: PrepBlock,
    functions: Mapping[str, object] | None,
    source: Path,
) -> object | None:
    if functions is None or not block.function_name:
        return None
    function = functions.get(block.function_name)
    # The flattened frontend can contain equal source names from different
    # modules. Select the declaration belonging to this ASM block.
    return next(
        (
            candidate for candidate in functions.values()
            if getattr(candidate, 'name', None) == block.function_name
            and getattr(candidate, 'module_path', None) is not None
            and Path(candidate.module_path).resolve() == source
        ),
        function,
    )


def _label_definitions(block: PrepBlock) -> list[tuple[str, int]]:
    definitions: list[tuple[str, int]] = []
    for offset, line in enumerate(block.body.splitlines(), start=1):
        match = _LABEL_DEFINITION_RE.match(line)
        if match is None:
            continue
        label = match.group('label')
        if label.startswith('.L'):
            continue
        definitions.append((label, block.line + offset))
    return definitions


def _validate_unit_labels(
    blocks: Sequence[PrepBlock],
    functions: Mapping[str, object] | None,
) -> None:
    """Reject non-local labels that collide inside one generated ASM unit."""
    seen: dict[str, tuple[PrepBlock, int]] = {}
    generated_symbols: dict[str, PrepBlock] = {}
    for block in blocks:
        function = _function_for_block(block, functions, block.source.resolve())
        if function is not None:
            symbol = _assembly_symbol_name(block, function)
            previous = generated_symbols.get(symbol)
            if previous is not None:
                raise PrepError(
                    f'{block.source}:{block.line}: el simbolo ASM generado '
                    f'{symbol!r} se repite en las funciones '
                    f'{previous.function_name!r} y {block.function_name!r}'
                )
            generated_symbols[symbol] = block

        for label, line in _label_definitions(block):
            previous = seen.get(label)
            if previous is not None:
                previous_block, previous_line = previous
                raise PrepError(
                    f'{block.source}:{line}: la etiqueta ASM no local '
                    f'{label!r} de la funcion {block.function_name!r} colisiona '
                    f'con {previous_block.source}:{previous_line} en la funcion '
                    f'{previous_block.function_name!r}; usa una etiqueta .L... '
                    'o un nombre unico'
                )
            seen[label] = (block, line)

    for label, (block, line) in seen.items():
        if label in generated_symbols:
            owner = generated_symbols[label]
            raise PrepError(
                f'{block.source}:{line}: la etiqueta ASM {label!r} '
                f'colisiona con el simbolo generado de la funcion '
                f'{owner.function_name!r}; usa un nombre de etiqueta unico'
            )


def _render_assembly_unit(
    blocks: Sequence[PrepBlock],
    functions: Mapping[str, object] | None,
    target_triple: str | None,
    abi: str | None,
) -> tuple[str, tuple[PrepBlockMetadata, ...]]:
    _validate_unit_labels(blocks, functions)
    lines: list[str] = []
    metadata: list[PrepBlockMetadata] = []

    for block in blocks:
        source = block.source.resolve()
        function = _function_for_block(block, functions, source)
        start = len(lines) + 1
        if function is not None and target_triple is not None:
            block_lines, header_count, body_count = _render_assembly_lines(
                block,
                function,
                target_triple,
                abi,
            )
        else:
            block_lines = block.body.rstrip('\r\n').splitlines()
            header_count = 0
            body_count = len(block_lines)

        lines.extend(block_lines)
        body_start = start + header_count if body_count else start
        body_end = body_start + body_count - 1 if body_count else body_start - 1
        metadata.append(
            PrepBlockMetadata(
                source=block.source,
                function_name=block.function_name,
                dialect=block.dialect,
                line=block.line,
                generated_start=start,
                generated_body_start=body_start,
                generated_body_end=body_end,
                generated_end=len(lines),
            )
        )

    return '\n'.join(lines), tuple(metadata)


def write_prep_files(
    blocks: Sequence[PrepBlock],
    project_root: Path,
    build_root: Path | None = None,
    functions: Mapping[str, object] | None = None,
    target_triple: str | None = None,
    abi: str | None = None,
    metadata: MutableMapping[Path, tuple[PrepBlockMetadata, ...]] | None = None,
) -> list[Path]:
    """Write one grouped `.asm` unit for every source file containing ASM."""
    root = build_root or project_root / 'build' / 'prep'
    written: list[Path] = []
    cleaned_directories: set[Path] = set()
    grouped: dict[Path, list[PrepBlock]] = {}

    if metadata is not None:
        metadata.clear()

    for block in blocks:
        grouped.setdefault(block.source.resolve(), []).append(block)

    cleanup_patterns = (
        '*__prep_*.asm',
        '*__prep_*.obj',
        '*__prep_*.o',
        '*__prep.asm',
        '*__prep.obj',
        '*__prep.o',
    )

    if not blocks:
        if root.exists():
            for pattern in cleanup_patterns:
                for previous in root.rglob(pattern):
                    previous.unlink()
        return written

    for source, source_blocks in grouped.items():
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
            for pattern in cleanup_patterns:
                for previous in module_dir.glob(pattern):
                    previous.unlink()
            cleaned_directories.add(module_dir)

        destination = module_dir / f'{_safe_component(source.stem)}__prep.asm'
        content, block_metadata = _render_assembly_unit(
            source_blocks,
            functions,
            target_triple,
            abi,
        )
        destination.write_text(content, encoding='utf-8')
        written.append(destination)
        if metadata is not None:
            metadata[destination] = block_metadata

    return written


__all__ = [
    'PrepBlock',
    'PrepBlockMetadata',
    'PrepError',
    'extract_prep_blocks',
    'preprocess_conditionals',
    'write_prep_files',
]

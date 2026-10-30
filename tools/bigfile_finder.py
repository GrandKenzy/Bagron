"""Find large Python files by counting lines that contain source content."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import io
import json
import os
import sys
import tokenize
from pathlib import Path


DEFAULT_THRESHOLD = 500
WORK_DIRECTORIES = {'core', 'tests', 'tools'}
SKIPPED_DIRECTORIES = {
    '.git',
    '.venv',
    '__pycache__',
    'build',
    'log',
    'node_modules',
    'vendor',
    'venv',
}
IGNORED_TOKEN_TYPES = {
    tokenize.COMMENT,
    tokenize.DEDENT,
    tokenize.ENDMARKER,
    tokenize.INDENT,
    tokenize.NEWLINE,
    tokenize.NL,
}


@dataclass(frozen=True)
class FileStats:
    """Detailed line statistics for one Python file."""

    name: str
    path: str
    relative_path: str
    physical_lines: int
    blank_lines: int
    comment_lines: int
    comment_only_lines: int
    content_lines: int


def _python_files(root: Path):
    """Yield Python files from project work directories only."""
    restrict_to_project_work = root.name not in WORK_DIRECTORIES
    for current, directory_names, file_names in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current_path = Path(current)
        if restrict_to_project_work and current_path == root:
            directory_names[:] = [
                name for name in directory_names
                if name in WORK_DIRECTORIES
            ]
        else:
            directory_names[:] = [
                name
                for name in directory_names
                if name not in SKIPPED_DIRECTORIES
                and not (current_path / name).is_symlink()
            ]
        for name in sorted(file_names):
            candidate = current_path / name
            if candidate.suffix == '.py' and not candidate.is_symlink():
                yield candidate


def _fallback_line_sets(source: str) -> tuple[set[int], set[int], set[int]]:
    """Build line sets for invalid Python input without executing it."""
    blank_lines: set[int] = set()
    comment_only_lines: set[int] = set()
    content_lines: set[int] = set()
    for number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            blank_lines.add(number)
        elif stripped.startswith('#'):
            comment_only_lines.add(number)
        else:
            content_lines.add(number)
    return blank_lines, comment_only_lines, content_lines


def _line_stats(source: str) -> tuple[int, int, int, int, int]:
    """Return physical, blank, comment, comment-only and content counts."""
    lines = source.splitlines()
    physical_lines = len(lines)
    blank_lines = {
        number
        for number, line in enumerate(lines, start=1)
        if not line.strip()
    }
    comment_lines: set[int] = set()
    content_lines: set[int] = set()

    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                comment_lines.add(token.start[0])
                continue
            if token.type in IGNORED_TOKEN_TYPES:
                continue
            if token.string.strip():
                content_lines.add(token.start[0])
    except tokenize.TokenError:
        fallback_blank, comment_only, fallback_content = (
            _fallback_line_sets(source)
        )
        blank_lines = fallback_blank
        content_lines = fallback_content
        comment_lines.update(comment_only)

    comment_only_lines = comment_lines - content_lines
    return (
        physical_lines,
        len(blank_lines),
        len(comment_lines),
        len(comment_only_lines),
        len(content_lines),
    )


def file_stats(path: Path, root: Path) -> FileStats:
    """Analyze one Python file and return detailed line statistics."""
    source = ''
    try:
        with tokenize.open(path) as stream:
            source = stream.read()
    except (OSError, SyntaxError, UnicodeDecodeError):
        source = path.read_text(encoding='utf-8', errors='replace')

    physical, blank, comments, comment_only, content = _line_stats(source)
    return FileStats(
        name=path.name,
        path=str(path.resolve()),
        relative_path=str(path.relative_to(root)),
        physical_lines=physical,
        blank_lines=blank,
        comment_lines=comments,
        comment_only_lines=comment_only,
        content_lines=content,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            'Busca archivos .py grandes contando solo líneas con contenido '
            'de código.'
        )
    )
    parser.add_argument(
        'root',
        nargs='?',
        type=Path,
        default=Path.cwd(),
        help='directorio raíz; por defecto, el directorio actual',
    )
    parser.add_argument(
        '--threshold',
        type=int,
        default=DEFAULT_THRESHOLD,
        help=(
            'mínimo de líneas con contenido para informar un archivo '
            f'(por defecto: {DEFAULT_THRESHOLD})'
        ),
    )
    parser.add_argument(
        '--format',
        choices=('text', 'json'),
        default='text',
        help='formato de salida; por defecto: text',
    )
    args = parser.parse_args()

    if args.threshold < 1:
        parser.error('--threshold debe ser mayor que cero')

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error(f'El directorio raíz no existe: {root}')

    results = [
        file_stats(path, root)
        for path in _python_files(root)
    ]
    results = [item for item in results if item.content_lines >= args.threshold]
    results.sort(key=lambda item: (-item.content_lines, item.path.lower()))

    if args.format == 'json':
        json.dump(
            {
                'root': str(root),
                'threshold': args.threshold,
                'scope': sorted(WORK_DIRECTORIES),
                'files': [asdict(item) for item in results],
                'total': len(results),
            },
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        print()
        return 0

    if not results:
        print(
            f'No se encontraron archivos .py con al menos '
            f'{args.threshold} líneas con contenido en {root}'
        )
        return 0

    print(f'Raíz: {root}')
    print(f'Umbral: {args.threshold} líneas con contenido')
    print(f'Archivos detectados: {len(results)}')
    for item in results:
        print(f'\n- {item.name}')
        print(f'  ruta: {item.path}')
        print(f'  ruta_relativa: {item.relative_path}')
        print(f'  líneas_físicas: {item.physical_lines}')
        print(f'  líneas_vacías: {item.blank_lines}')
        print(f'  líneas_con_comentarios: {item.comment_lines}')
        print(f'  líneas_solo_comentario: {item.comment_only_lines}')
        print(f'  líneas_con_contenido: {item.content_lines}')
    print(f'Total: {len(results)} archivos.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

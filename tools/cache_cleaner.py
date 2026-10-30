"""Remove Python bytecode cache directories from a project tree."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


def _cache_directories(root: Path):
    """Yield real ``__pycache__`` directories without following symlinks."""
    for current, directory_names, _ in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current_path = Path(current)
        remaining: list[str] = []
        for name in directory_names:
            candidate = current_path / name
            if candidate.is_symlink():
                continue
            if name == '__pycache__':
                yield candidate
                continue
            remaining.append(name)
        directory_names[:] = remaining


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Borra carpetas __pycache__ dentro de un directorio.'
    )
    parser.add_argument(
        'root',
        nargs='?',
        type=Path,
        default=Path.cwd(),
        help='directorio raíz; por defecto, el directorio actual',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='muestra las carpetas que borraría sin modificar el disco',
    )
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error(f'El directorio raíz no existe: {root}')

    caches = sorted(_cache_directories(root))
    if not caches:
        print(f'No se encontraron carpetas __pycache__ en {root}')
        return 0

    for cache in caches:
        if args.dry_run:
            print(f'[dry-run] {cache}')
        else:
            shutil.rmtree(cache)
            print(f'Borrado: {cache}')

    action = 'se borrarían' if args.dry_run else 'borradas'
    print(f'{len(caches)} carpetas {action}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

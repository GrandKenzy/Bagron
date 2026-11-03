from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence


_LINK_DIRECTIVE_RE = re.compile(
    r'^[ \t]*#link[ \t]+'
    r'(?P<quote>["\'])(?P<path>.*?)\1[ \t]*$'
)


def _blank_line(line: str) -> str:
    return '\n' if line.endswith(('\n', '\r')) else ''


def _inside_project(path: Path, project_root: Path) -> bool:
    try:
        path.relative_to(project_root)
    except ValueError:
        return False
    return True


def extract_link_directives(
    lines: Sequence[str],
    source: Path,
    *,
    project_root: Path,
    allow: bool,
) -> tuple[list[str], list[Path], list[str]]:
    """Remove ``#link`` directives and resolve their project-local folders.

    Link directories are intentionally collected before Bagron parsing.  This
    keeps the directive out of the language grammar and makes it impossible
    for an imported module to inject a linker search path silently.
    """
    transformed: list[str] = []
    directories: list[Path] = []
    errors: list[str] = []
    source = source.resolve()
    project_root = project_root.resolve()

    for index, line in enumerate(lines):
        raw = line.rstrip('\r\n')
        if not raw.lstrip().startswith('#link'):
            transformed.append(line)
            continue

        match = _LINK_DIRECTIVE_RE.fullmatch(raw)
        if not allow:
            errors.append(
                f'{source}:{index + 1}: #link solo se permite en el modulo '
                'principal'
            )
            transformed.append(_blank_line(line))
            continue
        if match is None:
            errors.append(
                f'{source}:{index + 1}: #link requiere una ruta entre comillas, '
                'por ejemplo #link "./bins"'
            )
            transformed.append(_blank_line(line))
            continue

        raw_path = match.group('path').strip()
        if not raw_path:
            errors.append(
                f'{source}:{index + 1}: #link requiere una ruta de directorio '
                'no vacia'
            )
            transformed.append(_blank_line(line))
            continue
        candidate = Path(raw_path)
        if candidate.is_absolute():
            errors.append(
                f'{source}:{index + 1}: #link solo acepta rutas relativas '
                'dentro del proyecto'
            )
            transformed.append(_blank_line(line))
            continue

        # NOTA: 1) Probar primero relativo al proyecto local
        project_target = (source.parent / candidate).resolve()
        resolved: Path | None = None

        if _inside_project(project_target, project_root):
            if project_target.is_dir():
                resolved = project_target
            elif project_target.is_file():
                errors.append(
                    f'{source}:{index + 1}: #link requiere un directorio, no un '
                    f'archivo: {project_target}'
                )
                transformed.append(_blank_line(line))
                continue

        # NOTA: 2) Si no existe en el proyecto local, buscar en las carpetas de Bagron
        if resolved is None:
            from core.globvars import BAGRON_ROOT
            bagron_root = BAGRON_ROOT.resolve()
            bagron_candidates = [
                (bagron_root / 'libs' / candidate).resolve(),
                (bagron_root / 'modules' / candidate).resolve(),
                (bagron_root / candidate).resolve(),
            ]
            parts = candidate.parts
            if parts and parts[0].lower() == 'bagron' and len(parts) > 1:
                bagron_candidates.insert(0, (bagron_root.joinpath(*parts[1:])).resolve())

            for bg_cand in bagron_candidates:
                if _inside_project(bg_cand, bagron_root) and bg_cand.is_dir():
                    resolved = bg_cand
                    break

        if resolved is None:
            if _inside_project(project_target, project_root):
                errors.append(
                    f'{source}:{index + 1}: el directorio #link no existe: '
                    f'{project_target}'
                )
            else:
                errors.append(
                    f'{source}:{index + 1}: la ruta #link queda fuera del proyecto: '
                    f'{raw_path!r}'
                )
        elif resolved not in directories:
            directories.append(resolved)

        transformed.append(_blank_line(line))

    return transformed, directories, errors


__all__ = ['extract_link_directives']

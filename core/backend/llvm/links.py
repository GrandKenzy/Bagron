from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


class NativeLinkError(RuntimeError):
    """Raised when a project-local native dependency cannot be prepared."""


@dataclass(frozen=True)
class NativeLinkPlan:
    """Resolved linker arguments and runtime files for one build."""

    search_args: tuple[str, ...]
    library_args: tuple[str, ...]
    runtime_files: tuple[Path, ...]

    @property
    def has_runtime_files(self) -> bool:
        return bool(self.runtime_files)


_SYSTEM_LIBRARIES = {
    'windows': {
        'advapi32', 'bcrypt', 'comdlg32', 'gdi32', 'imm32', 'kernel32',
        'msvcrt', 'ole32', 'oleaut32', 'shell32', 'shlwapi', 'setupapi',
        'ucrt', 'ucrtbase', 'user32', 'version', 'winhttp', 'winmm',
        'ws2_32', 'xinput',
    },
    'linux': {
        'c', 'crypt', 'dl', 'gcc', 'gcc_s', 'm', 'nsl', 'pthread', 'rt',
        'stdc++', 'unwind', 'util',
    },
}


def _target_family(triple: str) -> str:
    normalized = str(triple).lower()
    if 'windows' in normalized or 'mingw' in normalized or 'msvc' in normalized:
        return 'windows'
    if 'linux' in normalized or 'gnu' in normalized or 'musl' in normalized:
        return 'linux'
    if 'darwin' in normalized or 'macos' in normalized:
        return 'darwin'
    return 'unknown'


def _split_link(link: str) -> tuple[str | None, str]:
    if ':' not in link:
        return None, link
    domain, library = link.split(':', 1)
    return domain, library


def _is_system_library(domain: str | None, library: str, family: str) -> bool:
    normalized = library.lower()
    if normalized in _SYSTEM_LIBRARIES.get(family, set()):
        return True
    # ``extern c`` is the C ABI, but only its conventional runtime names are
    # system-provided. Arbitrary C libraries remain project dependencies.
    return domain == 'c' and normalized in {
        'c', 'm', 'dl', 'pthread', 'rt', 'ucrt', 'ucrtbase', 'msvcrt',
    }


def _candidate_names(library: str, family: str) -> tuple[str, ...]:
    if family == 'windows':
        return (
            f'{library}.lib',
            f'lib{library}.dll.a',
            f'{library}.a',
            f'lib{library}.a',
        )
    if family == 'linux':
        return (f'lib{library}.so', f'lib{library}.a')
    if family == 'darwin':
        return (f'lib{library}.dylib', f'lib{library}.a')
    return ()


def _incompatible_names(library: str, family: str) -> tuple[str, ...]:
    if family == 'windows':
        return (f'lib{library}.so', f'{library}.so', f'{library}.dll')
    if family == 'linux':
        return (f'{library}.lib', f'{library}.dll', f'lib{library}.dll.a')
    if family == 'darwin':
        return (f'{library}.dll', f'{library}.lib', f'lib{library}.so')
    return ()


def _find_file(directory: Path, names: Iterable[str]) -> Path | None:
    for name in names:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def _windows_import_library(path: Path) -> bool:
    """Distinguish a COFF import library from a static ``.lib`` archive."""
    try:
        if b'__IMPORT_DESCRIPTOR_' in path.read_bytes():
            return True
    except OSError:
        return False

    llvm_nm = shutil.which('llvm-nm')
    if llvm_nm is None:
        return False
    try:
        result = subprocess.run(
            [llvm_nm, '--format=posix', str(path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    return '__IMPORT_DESCRIPTOR_' in (result.stdout or '')


def _runtime_for(
    link_file: Path,
    library: str,
    family: str,
) -> tuple[Path, ...]:
    if family == 'windows':
        requires_dll = link_file.name.lower().endswith('.dll.a') or (
            link_file.suffix.lower() == '.lib'
            and _windows_import_library(link_file)
        )
        if not requires_dll:
            return ()
        runtime = _find_file(
            link_file.parent,
            (f'{library}.dll', f'lib{library}.dll'),
        )
        if runtime is None:
            raise NativeLinkError(
                f'Falta la DLL de la libreria {library!r} junto a {link_file}'
            )
        return (runtime,)

    if family == 'linux' and (
        link_file.name.endswith('.so') or '.so.' in link_file.name
    ):
        resolved = link_file.resolve()
        return (link_file, resolved) if resolved != link_file else (link_file,)

    if family == 'darwin' and link_file.suffix.lower() == '.dylib':
        return (link_file,)
    return ()


def resolve_native_links(
    native_links: Sequence[str],
    link_directories: Sequence[Path],
    target_triple: str,
) -> NativeLinkPlan:
    """Resolve explicit project libraries without changing global search paths."""
    family = _target_family(target_triple)
    search_args = tuple(f'-L{Path(directory)}' for directory in link_directories)
    library_args: list[str] = []
    runtime_files: list[Path] = []
    runtime_names: dict[str, Path] = {}

    for link in native_links:
        domain, library = _split_link(link)
        library_args.append(f'-l{library}')
        if not link_directories or _is_system_library(domain, library, family):
            continue
        candidates = _candidate_names(library, family)
        if not candidates:
            raise NativeLinkError(
                f'No hay variantes de libreria configuradas para el target '
                f'{target_triple!r}'
            )

        link_file = next(
            (
                found
                for directory in link_directories
                if (found := _find_file(directory, candidates)) is not None
            ),
            None,
        )
        if link_file is None:
            incompatible = next(
                (
                    directory / name
                    for directory in link_directories
                    for name in _incompatible_names(library, family)
                    if (directory / name).is_file()
                ),
                None,
            )
            if incompatible is not None:
                raise NativeLinkError(
                    f'La libreria {library!r} es incompatible con el target '
                    f'{target_triple!r}: {incompatible}'
                )
            raise NativeLinkError(
                f'No se encontro la libreria {library!r} en las rutas #link: '
                + ', '.join(str(directory) for directory in link_directories)
            )

        for runtime in _runtime_for(link_file, library, family):
            previous = runtime_names.get(runtime.name)
            if previous is not None and previous != runtime:
                raise NativeLinkError(
                    f'Las librerias locales requieren runtimes con el mismo nombre '
                    f'pero procedencias distintas: {previous} y {runtime}'
                )
            if previous is None:
                runtime_names[runtime.name] = runtime
                runtime_files.append(runtime)

    return NativeLinkPlan(
        search_args=search_args,
        library_args=tuple(library_args),
        runtime_files=tuple(runtime_files),
    )


def copy_runtime_files(runtime_files: Sequence[Path], output_dir: Path) -> None:
    """Copy declared dynamic runtimes next to the produced executable."""
    for runtime in runtime_files:
        destination = output_dir / runtime.name
        try:
            shutil.copy2(runtime, destination)
        except OSError as error:
            raise NativeLinkError(
                f'No se pudo copiar la libreria dinamica {runtime} a '
                f'{destination}: {error}'
            ) from error


__all__ = [
    'NativeLinkError',
    'NativeLinkPlan',
    'copy_runtime_files',
    'resolve_native_links',
]

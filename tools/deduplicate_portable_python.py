"""Record portable Python aliases so PyInstaller does not bundle duplicate bytes.

The working runtime is left intact: vnma and compiler smoke tests can continue
running normally. PyInstaller omits aliases listed in the manifest, and the
installed runtime recreates them as symlinks (POSIX) or hardlinks (Windows).
"""

from __future__ import annotations

import argparse
import filecmp
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil

MANIFEST_NAME = 'bagron-runtime-aliases.json'
FORMAT_VERSION = 1

_LINUX_EXECUTABLE = re.compile(r'python(?:3(?:\.\d+)?)?$')
_LINUX_LIBRARY = re.compile(r'libpython\d+\.\d+\.so(?:\.\d+)*$')
_WINDOWS_EXECUTABLE = re.compile(r'python(?:3(?:\d+)?)?\.exe$', re.IGNORECASE)
_WINDOWS_LIBRARY = re.compile(r'python\d+\.dll$', re.IGNORECASE)


def _within(candidate: Path, root: Path) -> bool:
    return candidate == root or root in candidate.parents


def _safe_relative(value: str) -> Path:
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError(f'Unsafe portable runtime path: {value!r}')
    posix = PurePosixPath(value)
    if posix.is_absolute() or any(part in ('.', '..') for part in value.split('/')):
        raise ValueError(f'Unsafe portable runtime path: {value!r}')
    return Path(*posix.parts)


def _duplicate_family(path: Path, *, platform: str) -> str | None:
    relative = path.as_posix()
    parent, name = path.parent.as_posix(), path.name
    if platform == 'linux':
        if parent == 'bin' and _LINUX_EXECUTABLE.fullmatch(name):
            return 'python-executables'
        if parent == 'lib' and _LINUX_LIBRARY.fullmatch(name):
            return 'python-shared-library'
    elif platform == 'windows':
        if parent == '.' and _WINDOWS_EXECUTABLE.fullmatch(name):
            return 'python-executables'
        if parent == '.' and _WINDOWS_LIBRARY.fullmatch(name):
            return 'python-shared-library'
    return None


def make_manifest(runtime: Path, *, platform: str) -> dict:
    """Produce a validated map of alias path -> canonical path in the runtime."""
    if platform not in {'linux', 'windows'}:
        raise ValueError(f'Unsupported platform: {platform}')
    runtime = runtime.resolve(strict=True)
    aliases: dict[str, str] = {}
    groups: dict[str, list[Path]] = {}

    for candidate in sorted(runtime.rglob('*')):
        relative = candidate.relative_to(runtime)
        name = relative.as_posix()
        if name == MANIFEST_NAME:
            continue
        if candidate.is_symlink():
            # Preserve native directory/file aliases, but reject dangling links
            # and links that would reference the builder's temporary workspace.
            target = candidate.resolve(strict=True)
            if not _within(target, runtime):
                raise ValueError(f'Symlink escapes the Python runtime: {name}')
            aliases[name] = target.relative_to(runtime).as_posix()
            continue
        if not candidate.is_file():
            continue
        family = _duplicate_family(relative, platform=platform)
        if family:
            groups.setdefault(family, []).append(candidate)

    # Only collapse byte-identical files with established Python alias names.
    # Keep the canonical executable as python.exe on Windows and the actual
    # versioned binary on Linux (for example bin/python3.14).
    for family, paths in groups.items():
        if family == 'python-executables' and platform == 'windows':
            priority = lambda p: (p.name.lower() != 'python.exe', p.name)
        elif family == 'python-executables':
            priority = lambda p: (p.name.count('.') == 0, -len(p.name), p.name)
        else:
            priority = lambda p: (-len(p.name), p.name)
        accepted: list[Path] = []
        for candidate in sorted(paths, key=priority):
            canonical = next(
                (entry for entry in accepted if
                 entry.stat().st_size == candidate.stat().st_size and
                 filecmp.cmp(entry, candidate, shallow=False)),
                None,
            )
            if canonical is None:
                accepted.append(candidate)
            else:
                aliases[candidate.relative_to(runtime).as_posix()] = (
                    canonical.relative_to(runtime).as_posix()
                )

    for alias_name, canonical_name in aliases.items():
        alias = runtime / _safe_relative(alias_name)
        canonical = runtime / _safe_relative(canonical_name)
        if alias == canonical or not canonical.is_file() and not canonical.is_dir():
            raise ValueError(f'Invalid portable Python alias: {alias_name}')
        if canonical.is_symlink():
            raise ValueError(f'Alias target is not canonical: {canonical_name}')

    return {
        'format_version': FORMAT_VERSION,
        'platform': platform,
        'aliases': dict(sorted(aliases.items())),
    }


def verify_manifest(runtime: Path, *, expected_platform: str | None = None) -> dict[str, str]:
    """Validate alias paths and their canonical targets after PyInstaller extraction.

    It is legitimate for alias entries to be absent at this stage: those
    entries are intentionally omitted from the PyInstaller archive.
    """
    runtime = runtime.resolve(strict=True)
    manifest = json.loads((runtime / MANIFEST_NAME).read_text(encoding='utf-8'))
    if manifest.get('format_version') != FORMAT_VERSION:
        raise ValueError('Unsupported Python alias manifest format')
    if expected_platform is not None and manifest.get('platform') != expected_platform:
        raise ValueError('Python runtime alias manifest is for another platform')
    aliases = manifest.get('aliases')
    if not isinstance(aliases, dict):
        raise ValueError('Python runtime alias manifest must contain a mapping')
    result: dict[str, str] = {}
    for alias_name, canonical_name in aliases.items():
        alias = runtime / _safe_relative(alias_name)
        canonical = runtime / _safe_relative(canonical_name)
        if alias == canonical:
            raise ValueError(f'Python alias points to itself: {alias_name}')
        if not _within(alias.resolve(strict=False), runtime) or not _within(
            canonical.resolve(strict=True), runtime
        ):
            raise ValueError(f'Python alias escapes runtime: {alias_name}')
        if not canonical.is_file() and not canonical.is_dir():
            raise FileNotFoundError(f'Missing Python alias target: {canonical_name}')
        if canonical.is_symlink() or alias.is_symlink():
            raise ValueError(f'Nested or unexpected Python alias: {alias_name}')
        if alias.exists():
            # The installed runtime may have aliases restored. The shipped
            # PyInstaller payload must not contain duplicate alias files.
            raise ValueError(f'Unexpected duplicate Python alias: {alias_name}')
        result[alias_name] = canonical_name
    return result


def restore_aliases(runtime: Path, *, platform: str) -> int:
    """Restore missing aliases in an installed runtime (without network access).

    POSIX uses relative symlinks. Windows uses hardlinks on the same volume,
    falling back to copies when the filesystem does not support hardlinks.
    """
    runtime = runtime.resolve(strict=True)
    aliases = verify_manifest(runtime, expected_platform=platform)
    for alias_name, canonical_name in aliases.items():
        alias = runtime / _safe_relative(alias_name)
        canonical = runtime / _safe_relative(canonical_name)
        alias.parent.mkdir(parents=True, exist_ok=True)
        if platform == 'linux':
            alias.symlink_to(
                os.path.relpath(canonical, start=alias.parent),
                target_is_directory=canonical.is_dir(),
            )
        elif canonical.is_dir():
            shutil.copytree(canonical, alias)
        else:
            try:
                os.link(canonical, alias)
            except OSError:
                shutil.copy2(canonical, alias)

    # Validate all restored aliases, including the expected primary Python.
    for alias_name, canonical_name in aliases.items():
        alias = runtime / _safe_relative(alias_name)
        canonical = runtime / _safe_relative(canonical_name)
        if not alias.exists():
            raise RuntimeError(f'Python alias could not be restored: {alias_name}')
        if platform == 'linux' and (
            not alias.is_symlink() or alias.resolve() != canonical.resolve()
        ):
            raise RuntimeError(f'Invalid restored Python symlink: {alias_name}')
        if platform == 'windows' and canonical.is_file() and not filecmp.cmp(
            alias, canonical, shallow=False
        ):
            raise RuntimeError(f'Invalid restored Python alias: {alias_name}')
    return len(aliases)


def write_manifest(runtime: Path, *, platform: str) -> Path:
    runtime = runtime.resolve(strict=True)
    metadata = make_manifest(runtime, platform=platform)
    output = runtime / MANIFEST_NAME
    output.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(f'Portable Python aliases: {len(metadata["aliases"])}')
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--platform', choices=('linux', 'windows'), required=True)
    args = parser.parse_args()
    try:
        write_manifest(args.runtime, platform=args.platform)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

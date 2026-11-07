"""Versioned dependency lockfiles for Bagron projects."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


LOCK_FORMAT = 'bagron-lock@1'
_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
_MAX_LOCK_BYTES = 16 * 1024 * 1024


class LockfileError(RuntimeError):
    """Raised when a Bagron lockfile is malformed or does not match a package."""


def _package_name(value: object) -> str:
    name = str(value)
    if _NAME_RE.fullmatch(name) is None:
        raise LockfileError(f'El nombre de paquete del lockfile no es valido: {name!r}')
    return name


def _digest(value: object) -> str:
    digest = str(value).lower()
    if _SHA256_RE.fullmatch(digest) is None:
        raise LockfileError('El lockfile contiene un SHA-256 invalido')
    return digest


def _validate(data: object) -> dict[str, object]:
    if not isinstance(data, dict) or data.get('format') != LOCK_FORMAT:
        raise LockfileError(f'El lockfile debe usar el formato {LOCK_FORMAT!r}')
    packages = data.get('packages', {})
    if not isinstance(packages, dict):
        raise LockfileError('El lockfile no contiene una tabla packages valida')
    target = data.get('target', {})
    if not isinstance(target, dict):
        raise LockfileError('El lockfile no contiene un target valido')
    for raw_name, raw_entry in packages.items():
        name = _package_name(raw_name)
        if not isinstance(raw_entry, dict):
            raise LockfileError(f'La entrada bloqueada de {name!r} no es valida')
        if not str(raw_entry.get('version', '')).strip():
            raise LockfileError(f'La entrada bloqueada de {name!r} no tiene version')
        _digest(raw_entry.get('sha256', ''))
        package_format = raw_entry.get('package_format')
        if package_format not in {'lib1', 'lib2'}:
            raise LockfileError(f'La entrada bloqueada de {name!r} tiene un formato invalido')
        dependencies = raw_entry.get('dependencies', [])
        if not isinstance(dependencies, list):
            raise LockfileError(f'Las dependencias bloqueadas de {name!r} no son validas')
        for dependency in dependencies:
            _package_name(dependency)
    return data


def load_lockfile(project_root: str | Path) -> dict[str, object] | None:
    """Load and validate ``bagron.lock`` when the project provides one."""
    candidate = Path(project_root).resolve()
    path = candidate if candidate.is_file() or candidate.suffix == '.lock' else candidate / 'bagron.lock'
    if not path.is_file():
        return None
    try:
        if path.stat().st_size > _MAX_LOCK_BYTES:
            raise LockfileError('El lockfile supera el limite de tamaño permitido')
        data = json.loads(path.read_text(encoding='utf-8'))
    except LockfileError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LockfileError(f'No se pudo leer {path}: {error}') from error
    return _validate(data)


def validate_lock_target(
    lock_data: dict[str, object] | None,
    *,
    system: str,
    architecture: str,
) -> None:
    """Reject a lockfile selected for a different target when it is explicit."""
    if lock_data is None:
        return
    target = lock_data.get('target', {})
    if not isinstance(target, dict):
        raise LockfileError('El target del lockfile no es valido')
    for field, actual in (('system', system), ('architecture', architecture)):
        expected = str(target.get(field, 'auto')).strip().lower()
        if expected not in {'', 'auto', str(actual).strip().lower()}:
            raise LockfileError(
                f'El lockfile fija {field}={expected!r}, pero la compilacion usa {actual!r}'
            )


def validate_locked_package(
    lock_data: dict[str, object] | None,
    package: object,
) -> None:
    """Ensure the package selected by the compiler is exactly lock-pinned."""
    if lock_data is None:
        return
    packages = lock_data.get('packages', {})
    if not isinstance(packages, dict):
        raise LockfileError('El lockfile no contiene packages')
    name = str(getattr(package, 'name', ''))
    entry = packages.get(name)
    if not isinstance(entry, dict):
        raise LockfileError(f'La libreria {name!r} no aparece en bagron.lock')
    expected_version = str(entry.get('version', ''))
    actual_version = str(getattr(package, 'manifest', {}).get('version', ''))
    actual_digest = str(getattr(package, 'archive_sha256', '')).lower()
    actual_format = 'lib2' if int(getattr(package, 'library_version', 1)) == 2 else 'lib1'
    if expected_version != actual_version:
        raise LockfileError(
            f'La libreria {name!r} usa version {actual_version!r}, se esperaba {expected_version!r}'
        )
    if _digest(entry.get('sha256', '')) != actual_digest:
        raise LockfileError(f'El digest bloqueado de {name!r} no coincide con el paquete')
    if entry.get('package_format') != actual_format:
        raise LockfileError(f'El formato bloqueado de {name!r} no coincide con el paquete')


def update_lockfile(
    path: str | Path,
    *,
    name: str,
    version: str,
    source: str,
    package_format: str,
    data: bytes,
    dependencies: list[str] | None = None,
    system: str = 'auto',
    architecture: str = 'auto',
) -> Path:
    """Atomically add one verified package entry to a lockfile."""
    lock_path = Path(path).resolve()
    existing = load_lockfile(lock_path) if lock_path.is_file() else None
    payload = existing or {
        'format': LOCK_FORMAT,
        'target': {'system': system, 'architecture': architecture},
        'packages': {},
    }
    packages = payload.setdefault('packages', {})
    assert isinstance(packages, dict)
    package_name = _package_name(name)
    dependency_names = sorted({_package_name(item) for item in (dependencies or [])})
    packages[package_name] = {
        'version': str(version),
        'source': str(source),
        'sha256': hashlib.sha256(data).hexdigest(),
        'package_format': package_format,
        'dependencies': dependency_names,
    }
    validated = _validate(payload)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f'.{lock_path.name}.', suffix='.tmp', dir=lock_path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(validated, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, lock_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return lock_path


__all__ = [
    'LOCK_FORMAT',
    'LockfileError',
    'load_lockfile',
    'update_lockfile',
    'validate_lock_target',
    'validate_locked_package',
]

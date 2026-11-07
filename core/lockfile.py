"""Versioned dependency lockfiles for Bagron projects."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from contextlib import contextmanager


LOCK_FORMAT = 'bagron-lock@1'
_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
_MAX_LOCK_BYTES = 16 * 1024 * 1024
_LOCK_TIMEOUT = 60.0


class LockfileError(RuntimeError):
    """Raised when a Bagron lockfile is malformed or does not match a package."""


def _package_name(value: object) -> str:
    if not isinstance(value, str):
        raise LockfileError('El nombre de paquete del lockfile debe ser textual')
    name = value
    if _NAME_RE.fullmatch(name) is None:
        raise LockfileError(f'El nombre de paquete del lockfile no es valido: {name!r}')
    return name


def _digest(value: object) -> str:
    if not isinstance(value, str):
        raise LockfileError('El lockfile contiene un SHA-256 no textual')
    digest = value.lower()
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
    for field in ('system', 'architecture'):
        value = target.get(field, 'auto')
        if not isinstance(value, str) or not value.strip():
            raise LockfileError(f'El target del lockfile contiene {field} invalido')
    central_tuf = data.get('central_tuf')
    if central_tuf is not None:
        if not isinstance(central_tuf, dict):
            raise LockfileError('central_tuf del lockfile no es valido')
        metadata_version = central_tuf.get('targets_version')
        if isinstance(metadata_version, bool) or not isinstance(metadata_version, int) or metadata_version <= 0:
            raise LockfileError('La version TUF del lockfile no es valida')
    seen_names: set[str] = set()
    for raw_name, raw_entry in packages.items():
        name = _package_name(raw_name)
        if name.casefold() in seen_names:
            raise LockfileError(f'El lockfile contiene nombres de paquete duplicados: {name!r}')
        seen_names.add(name.casefold())
        if not isinstance(raw_entry, dict):
            raise LockfileError(f'La entrada bloqueada de {name!r} no es valida')
        version = raw_entry.get('version', '')
        if not isinstance(version, str) or not version.strip():
            raise LockfileError(f'La entrada bloqueada de {name!r} no tiene version')
        source = raw_entry.get('source', '')
        if not isinstance(source, str) or not source.strip():
            raise LockfileError(f'La entrada bloqueada de {name!r} no tiene origen')
        _digest(raw_entry.get('sha256', ''))
        package_format = raw_entry.get('package_format')
        if package_format not in {'lib1', 'lib2'}:
            raise LockfileError(f'La entrada bloqueada de {name!r} tiene un formato invalido')
        dependencies = raw_entry.get('dependencies', [])
        if not isinstance(dependencies, list):
            raise LockfileError(f'Las dependencias bloqueadas de {name!r} no son validas')
        seen_dependencies: set[str] = set()
        for dependency in dependencies:
            dependency_name = _package_name(dependency)
            if dependency_name.casefold() in seen_dependencies:
                raise LockfileError(
                    f'Las dependencias bloqueadas de {name!r} contienen duplicados'
                )
            seen_dependencies.add(dependency_name.casefold())
    return data


@contextmanager
def _lockfile_lock(lock_path: Path):
    """Serialize lockfile updates without trusting a pre-existing lock marker."""
    started = time.monotonic()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        if lock_path.is_symlink():
            raise LockfileError(f'El bloqueo del lockfile es un enlace simbolico: {lock_path}')
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(descriptor, str(os.getpid()).encode('ascii'))
            finally:
                os.close(descriptor)
            break
        except FileExistsError:
            try:
                owner_pid = int(lock_path.read_text(encoding='ascii').strip())
                if owner_pid != os.getpid():
                    try:
                        os.kill(owner_pid, 0)
                    except OSError:
                        lock_path.unlink(missing_ok=True)
                        continue
            except (OSError, UnicodeDecodeError, ValueError):
                pass
            if time.monotonic() - started >= _LOCK_TIMEOUT:
                raise LockfileError(f'No se pudo adquirir el bloqueo del lockfile: {lock_path}')
            time.sleep(0.05)
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def _reject_symlink_ancestors(path: Path) -> None:
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise LockfileError(f'La ruta del lockfile contiene un enlace simbolico: {candidate}')


def load_lockfile(project_root: str | Path) -> dict[str, object] | None:
    """Load and validate ``bagron.lock`` when the project provides one."""
    candidate = Path(project_root)
    path = candidate if candidate.is_file() or candidate.suffix == '.lock' else candidate / 'bagron.lock'
    if path.is_symlink():
        raise LockfileError(f'El lockfile es un enlace simbolico: {path}')
    path = path.resolve()
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
        raw_expected = target.get(field, 'auto')
        if not isinstance(raw_expected, str):
            raise LockfileError(f'El lockfile fija {field} con un valor no textual')
        expected = raw_expected.strip().lower()
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
    name = getattr(package, 'name', '')
    if not isinstance(name, str):
        raise LockfileError('La libreria seleccionada no tiene un nombre textual')
    entry = packages.get(name)
    if not isinstance(entry, dict):
        raise LockfileError(f'La libreria {name!r} no aparece en bagron.lock')
    expected_version = entry.get('version', '')
    actual_manifest = getattr(package, 'manifest', {})
    if not isinstance(actual_manifest, dict):
        raise LockfileError(f'La libreria {name!r} no contiene un manifest valido')
    actual_version = actual_manifest.get('version', '')
    actual_digest = getattr(package, 'archive_sha256', '')
    actual_format = 'lib2' if getattr(package, 'library_version', 1) == 2 else 'lib1'
    if not isinstance(expected_version, str) or not isinstance(actual_version, str):
        raise LockfileError(f'La libreria {name!r} tiene una version no textual')
    if not isinstance(actual_digest, str):
        raise LockfileError(f'La libreria {name!r} no tiene un digest textual')
    actual_digest = actual_digest.lower()
    if expected_version != actual_version:
        raise LockfileError(
            f'La libreria {name!r} usa version {actual_version!r}, se esperaba {expected_version!r}'
        )
    if _digest(entry.get('sha256', '')) != actual_digest:
        raise LockfileError(f'El digest bloqueado de {name!r} no coincide con el paquete')
    if entry.get('package_format') != actual_format:
        raise LockfileError(f'El formato bloqueado de {name!r} no coincide con el paquete')

    if 'dependencies' in actual_manifest:
        raw_dependencies = actual_manifest.get('dependencies')
        if not isinstance(raw_dependencies, list):
            raise LockfileError(f'Las dependencias de {name!r} no son validas')
        actual_dependencies = sorted(_package_name(item) for item in raw_dependencies)
        locked_dependencies = sorted(
            _package_name(item) for item in entry.get('dependencies', [])
        )
        if actual_dependencies != locked_dependencies:
            raise LockfileError(
                f'Las dependencias bloqueadas de {name!r} no coinciden con el paquete'
            )


def validate_lock_graph(
    lock_data: dict[str, object] | None,
    packages: object,
) -> None:
    """Check that every loaded package has all lockfile edges available."""
    if lock_data is None:
        return
    locked = lock_data.get('packages', {})
    if not isinstance(locked, dict):
        raise LockfileError('El lockfile no contiene packages')
    for package in packages:
        validate_locked_package(lock_data, package)
        name = getattr(package, 'name', '')
        entry = locked.get(name)
        if not isinstance(entry, dict):
            continue
        for dependency in entry.get('dependencies', []):
            dependency_name = _package_name(dependency)
            if dependency_name not in locked:
                raise LockfileError(
                    f'La dependencia transitiva {dependency_name!r} de {name!r} '
                    'no aparece en bagron.lock'
                )


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
    tuf_version: int | None = None,
) -> Path:
    """Atomically add one verified package entry to a lockfile."""
    raw_lock_path = Path(path)
    _reject_symlink_ancestors(raw_lock_path)
    lock_path = raw_lock_path.resolve()
    package_name = _package_name(name)
    if not isinstance(version, str) or not version.strip():
        raise LockfileError('La version del lockfile debe ser textual')
    if not isinstance(source, str) or not source.strip():
        raise LockfileError('El origen del lockfile debe ser textual')
    if package_format not in {'lib1', 'lib2'}:
        raise LockfileError('El formato del lockfile no es valido')
    if tuf_version is not None and (
        isinstance(tuf_version, bool) or not isinstance(tuf_version, int) or tuf_version <= 0
    ):
        raise LockfileError('La version TUF del lockfile no es valida')
    if dependencies is not None and not isinstance(dependencies, list):
        raise LockfileError('Las dependencias del lockfile deben ser una lista')
    dependency_names = sorted({_package_name(item) for item in (dependencies or [])})
    lock_marker = lock_path.with_name(f'.{lock_path.name}.lock')
    with _lockfile_lock(lock_marker):
        existing = load_lockfile(lock_path) if lock_path.is_file() else None
        payload = existing or {
            'format': LOCK_FORMAT,
            'target': {'system': system, 'architecture': architecture},
            'packages': {},
        }
        packages = payload.setdefault('packages', {})
        assert isinstance(packages, dict)
        existing_tuf = payload.get('central_tuf')
        if tuf_version is not None:
            if isinstance(existing_tuf, dict):
                previous_tuf_version = existing_tuf.get('targets_version')
                if isinstance(previous_tuf_version, int) and tuf_version < previous_tuf_version:
                    raise LockfileError('La version TUF nueva es anterior a la del lockfile')
            payload['central_tuf'] = {'targets_version': tuf_version}
        packages[package_name] = {
            'version': version,
            'source': source,
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
            if lock_path.is_symlink():
                raise LockfileError(f'El lockfile de destino es un enlace simbolico: {lock_path}')
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
    'validate_lock_graph',
]

"""Herramientas de gestión y sincronización para repositorios de alojamiento Bagron (hostutils).

Automatiza la detección de artefactos modificados en build/, el cálculo de SHA-256,
tamaños y formatos, la solicitud interactiva de nuevas versiones y la generación
atómica de los manifiestos en discentra_central/ (packages.toml y manifest.toml).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
import tomllib
from typing import Callable
import zipfile


class HostingError(RuntimeError):
    """Excepción para errores en operaciones de repositorios de alojamiento."""


_BGLIB_MAGIC = b'BGLIB1\0\0'
_BGLIB_HEADER = struct.Struct('<8sHHBBHQQ32s32s32s32s32s')
_SEMVER_RE = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')


def _atomic_write_texts(updates: list[tuple[Path, str]]) -> None:
    """Publica varios archivos con temporales y rollback ante una sustitución fallida."""
    staged: list[tuple[Path, Path, Path | None]] = []
    replaced: list[Path] = []
    try:
        for destination, content in updates:
            destination.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(
                prefix=f'.{destination.stem}.',
                suffix='.tmp',
                dir=destination.parent,
                text=True,
            )
            temp_path = Path(temp_name)
            backup_path: Path | None = None
            try:
                with os.fdopen(fd, 'w', encoding='utf-8', newline='') as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                if destination.exists():
                    backup_fd, backup_name = tempfile.mkstemp(
                        prefix=f'.{destination.stem}.',
                        suffix='.bak',
                        dir=destination.parent,
                    )
                    os.close(backup_fd)
                    backup_path = Path(backup_name)
                    shutil.copy2(destination, backup_path)
            except Exception:
                temp_path.unlink(missing_ok=True)
                if backup_path:
                    backup_path.unlink(missing_ok=True)
                raise
            staged.append((destination, temp_path, backup_path))

        for destination, temp_path, _ in staged:
            os.replace(temp_path, destination)
            replaced.append(destination)
    except Exception:
        for destination, _, backup_path in reversed(staged):
            if destination not in replaced:
                continue
            if backup_path is None:
                destination.unlink(missing_ok=True)
            else:
                os.replace(backup_path, destination)
        raise
    finally:
        for _, temp_path, backup_path in staged:
            temp_path.unlink(missing_ok=True)
            if backup_path:
                backup_path.unlink(missing_ok=True)


def _atomic_write_text(destination: Path, content: str) -> None:
    """Publica un archivo de texto mediante un temporal del mismo directorio."""
    _atomic_write_texts([(destination, content)])


def _fsync_directory(directory: Path) -> None:
    """Best-effort fsync for the directory containing a published artifact."""
    if os.name == 'nt':
        return
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _pack_library_atomically(
    packer: Callable[..., Path],
    source: Path,
    destination: Path,
    *,
    name: str,
    version: str,
) -> Path:
    """Package and verify a library before publishing it into ``build/``."""
    from core.library import LibraryError, verify_library

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise HostingError(f'El artefacto de destino es un enlace simbólico: {destination}')
    temporary_root = Path(tempfile.mkdtemp(
        prefix=f'.{destination.stem}.',
        dir=destination.parent,
    ))
    temporary = temporary_root / destination.name
    try:
        result = Path(packer(source, temporary, name=name, version=version)).resolve()
        if result != temporary.resolve() or not result.is_file():
            raise HostingError('El empaquetador no produjo el artefacto temporal esperado.')
        try:
            package = verify_library(result)
        except LibraryError as error:
            raise HostingError(f'El artefacto generado no supera la verificación: {error}') from error
        if package.name != name or str(package.manifest.get('version', '')) != version:
            raise HostingError(
                'El artefacto generado no coincide con el nombre o versión solicitados.'
            )
        with result.open('rb+') as handle:
            os.fsync(handle.fileno())
        os.replace(result, destination)
        _fsync_directory(destination.parent)
        return destination
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def _inspect_hosted_artifact(file_path: Path) -> dict[str, object]:
    """Inspect binaries and fully verify every Bagron library artifact."""
    artifact = inspect_build_artifact(file_path)
    if file_path.suffix.lower() == '.lib' or artifact['format'] in {'lib1', 'lib2'}:
        from core.library import LibraryError, verify_library
        try:
            package = verify_library(file_path)
        except LibraryError as error:
            raise HostingError(f'El artefacto de librería {file_path.name} no es válido: {error}') from error
        artifact['name'] = package.name
        artifact['internal_version'] = package.manifest.get('version')
        artifact['format'] = 'lib2' if package.library_version == 2 else 'lib1'
        artifact['kind'] = 'librería'
    return artifact


def validate_semver(version: object, *, context: str = 'Versión') -> str:
    """Valida una versión estable con el formato MAJOR.MINOR.PATCH."""
    if not isinstance(version, str):
        raise HostingError(f'{context} inválida: se esperaba texto MAJOR.MINOR.PATCH.')
    normalized = version.strip()
    if _SEMVER_RE.fullmatch(normalized) is None:
        raise HostingError(
            f'{context} inválida: {version!r}. Usa el formato MAJOR.MINOR.PATCH, por ejemplo 1.2.3.'
        )
    return normalized


def bump_semver_patch(version: str) -> str:
    """Incrementa el componente patch de una versión SemVer (ej. 1.1.4 -> 1.1.5)."""
    major, minor, patch = (int(part) for part in validate_semver(version).split('.'))
    return f'{major}.{minor}.{patch + 1}'


def _prompt_changed_version(
    name: str,
    current_version: str,
    suggested_version: str,
    *,
    input_fn: Callable[[str], str],
    print_fn: Callable[[str], None],
) -> str:
    """Solicita solo la versión de un paquete cuyo artefacto cambió."""
    current = validate_semver(current_version, context=f'Versión actual de {name}')
    suggested = validate_semver(suggested_version, context=f'Versión sugerida de {name}')
    prompt = f'set version from {name} {current}: '
    while True:
        raw = input_fn(prompt)
        candidate = suggested if isinstance(raw, str) and not raw.strip() else raw
        try:
            return validate_semver(candidate, context=f'Versión de {name}')
        except HostingError as error:
            print_fn(f'  [hostutils] {error}')


def _select_changed_version(
    name: str,
    current_version: str,
    suggested_version: str,
    *,
    auto_patch: bool,
    set_versions: dict[str, str],
    input_fn: Callable[[str], str],
    print_fn: Callable[[str], None],
) -> str:
    """Resuelve la versión de un paquete modificado y valida cualquier entrada."""
    current = validate_semver(current_version, context=f'Versión actual de {name}')
    suggested = validate_semver(suggested_version, context=f'Versión sugerida de {name}')
    if name in set_versions:
        version = validate_semver(set_versions[name], context=f'Versión fijada de {name}')
        print_fn(f'  [hostutils] {name}: versión fijada a {version}')
        return version
    if auto_patch:
        print_fn(f'  [hostutils] {name}: cambio detectado -> auto-bump patch {current} -> {suggested}')
        return suggested
    return _prompt_changed_version(
        name,
        current,
        suggested,
        input_fn=input_fn,
        print_fn=print_fn,
    )


def _repack_lib1_artifact_atomically(
    artifact_path: Path,
    *,
    name: str,
    version: str,
) -> None:
    """Regenera un lib1 desde sus fuentes internas para alinear su versión."""
    from core.library import LibraryError, pack_library, unpack_library, verify_library

    try:
        package = verify_library(artifact_path)
        if package.library_version != 1:
            raise HostingError(
                f'La librería {artifact_path.name} es lib2 y no puede versionarse sin recompilarse.'
            )
        with tempfile.TemporaryDirectory(prefix='bagron-hostutils-repack-') as temp_dir:
            root = Path(temp_dir)
            extracted = root / 'extracted'
            source = root / 'source'
            unpack_library(artifact_path, extracted)
            source.mkdir()
            for item in package.manifest.get('files', ()):
                if not isinstance(item, dict) or not isinstance(item.get('path'), str):
                    raise HostingError('El manifest lib1 contiene una entrada de archivo inválida.')
                member = item['path']
                if member.startswith('source/'):
                    relative = member.removeprefix('source/')
                else:
                    relative = member
                source_file = extracted.joinpath(*Path(member).parts)
                if not source_file.is_file():
                    raise HostingError(f'Falta el archivo {member!r} dentro de {artifact_path.name}.')
                destination = source.joinpath(*Path(relative).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source_file.read_bytes())
            _pack_library_atomically(
                pack_library,
                source,
                artifact_path,
                name=name,
                version=version,
            )
    except LibraryError as error:
        raise HostingError(
            f'No se pudo reconstruir {artifact_path.name} para la versión {version}: {error}'
        ) from error


def _align_artifact_version(
    artifact_path: Path,
    artifact: dict[str, object],
    *,
    name: str,
    version: str,
    dry_run: bool = False,
) -> dict[str, object]:
    """Alinea la versión interna de una librería con la metadata de Central."""
    version = validate_semver(version, context=f'Versión de {name}')
    format_name = str(artifact.get('format', ''))
    internal = artifact.get('internal_version')
    if format_name not in {'lib1', 'lib2'}:
        return artifact
    internal_version = validate_semver(
        internal,
        context=f'Versión interna de {artifact_path.name}',
    )
    if internal_version == version:
        return artifact
    if format_name == 'lib2':
        raise HostingError(
            f'La versión de Central para {name} sería {version}, pero {artifact_path.name} '
            f'contiene internamente {internal_version}. Recompila la lib2 con la versión elegida.'
        )
    if dry_run:
        with tempfile.TemporaryDirectory(prefix='bagron-hostutils-preview-') as temp_dir:
            temporary_artifact = Path(temp_dir) / artifact_path.name
            shutil.copy2(artifact_path, temporary_artifact)
            _repack_lib1_artifact_atomically(
                temporary_artifact,
                name=name,
                version=version,
            )
            return _inspect_hosted_artifact(temporary_artifact)
    _repack_lib1_artifact_atomically(artifact_path, name=name, version=version)
    return _inspect_hosted_artifact(artifact_path)


def inspect_build_artifact(file_path: Path) -> dict[str, object]:
    """Inspecciona un artefacto en build/ y obtiene hash, tamaño, formato y metadatos."""
    data = file_path.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    size_bytes = len(data)

    format_name = 'binary'
    kind_name = 'binario'
    source_sha = sha256
    internal_version = None

    if len(data) >= _BGLIB_HEADER.size and data[:8] == _BGLIB_MAGIC:
        unpacked = _BGLIB_HEADER.unpack(data[:_BGLIB_HEADER.size])
        kind_byte = unpacked[3]
        format_name = 'lib2' if kind_byte == 2 else 'lib1'
        kind_name = 'librería'
        source_sha = unpacked[11].hex()

        zip_offset = unpacked[6]
        zip_size = unpacked[7]
        try:
            with zipfile.ZipFile(file_path, 'r') as archive:
                if 'manifest.json' in archive.namelist():
                    manifest_data = json.loads(archive.read('manifest.json').decode('utf-8'))
                    internal_version = manifest_data.get('version')
                    if 'source_sha256' in manifest_data:
                        source_sha = manifest_data['source_sha256']
        except Exception:
            pass

    return {
        'name': file_path.stem,
        'file': file_path.name,
        'path': file_path,
        'sha256': sha256,
        'size_bytes': size_bytes,
        'format': format_name,
        'kind': kind_name,
        'source_sha': source_sha,
        'internal_version': internal_version,
    }


def compute_author_signature(
    author: str,
    package_name: str,
    version: str,
    source_or_artifact_sha: str,
    prefix: str = 'sha256',
) -> str:
    """Calcula la firma canónica de autor para un paquete en un repositorio de alojamiento."""
    sig_digest = hashlib.sha256()
    sig_digest.update(str(author).encode('utf-8'))
    sig_digest.update(b'\0')
    sig_digest.update(str(package_name).encode('utf-8'))
    sig_digest.update(b'\0')
    sig_digest.update(str(version).encode('utf-8'))
    sig_digest.update(b'\0')
    sig_digest.update(str(source_or_artifact_sha).encode('utf-8'))
    return f'{prefix}:{sig_digest.hexdigest()}'


def load_manifest_json(json_path: Path) -> dict[str, object]:
    """Carga discentra_central/manifest.json si existe."""
    if not json_path.is_file():
        return {}
    try:
        return json.loads(json_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise HostingError(f'Error al parsear {json_path}: {exc}') from exc


def render_packages_toml(
    repository: dict[str, str],
    packages: list[dict[str, object]],
) -> str:
    """Genera el contenido de discentra_central/packages.toml."""
    repo_name = repository.get("name", "bagronlab")
    repo_desc = repository.get("description", "Suite de paquetes Bagron")
    repo_author = repository.get("author", "Discentra Community")
    lines = [
        f'# Configuración de integración de {repo_name} con Central',
        '[repository]',
        f'name = "{repo_name}"',
        f'description = "{repo_desc}"',
        f'author = "{repo_author}"',
        '',
    ]

    for pkg in packages:
        name = pkg['name']
        lines.append(f'# Paquete: {name}')
        lines.append('[[packages]]')
        lines.append(f'name = "{name}"')
        lines.append(f'version = "{pkg.get("version", "1.0.0")}"')
        lines.append(f'kind = "{pkg.get("kind", "librería")}"')
        lines.append(f'format = "{pkg.get("format", "lib1")}"')
        lines.append(f'file = "{pkg.get("file", f"{name}.lib")}"')
        lines.append(f'description = "{pkg.get("description", "")}"')
        lines.append(f'license = "{pkg.get("license", "MIT")}"')
        lines.append('')

    return '\r\n'.join(lines).rstrip() + '\r\n'


def render_manifest_toml(
    manifest_meta: dict[str, str],
    packages: list[dict[str, object]],
) -> str:
    """Genera el contenido de discentra_central/manifest.toml."""
    lines = [
        '# Manifiesto de integridad criptográfica y firmas de autor para Central',
        '[manifest]',
        f'format = "{manifest_meta.get("format", "bagron-manifest@1")}"',
        f'hash_algorithm = "{manifest_meta.get("hash_algorithm", "sha256")}"',
        f'author = "{manifest_meta.get("author", "Discentra Community")}"',
        '',
    ]

    for pkg in packages:
        name = pkg['name']
        lines.append(f'# Verificación para: {name}')
        lines.append('[[packages]]')
        lines.append(f'name = "{name}"')
        lines.append(f'file = "{pkg.get("file", f"{name}.lib")}"')
        lines.append(f'format = "{pkg.get("format", "lib1")}"')
        lines.append(f'sha256 = "{pkg.get("sha256", "")}"')
        lines.append(f'size_bytes = {int(pkg.get("size_bytes", 0))}')
        lines.append(f'signature = "{pkg.get("signature", "")}"')
        lines.append('')

    return '\r\n'.join(lines).rstrip() + '\r\n'




def _update_toml_field(text: str, key: str, value: str, section: str = 'package') -> str:
    """Actualiza o inserta un campo dentro de una seccion de un archivo TOML."""
    pattern = r"(?m)(^\s*" + re.escape(key) + r"\s*=\s*)(?:\"[^\"]*\"|'[^']*'|[^\r\n#]+)"
    if re.search(pattern, text):
        return re.sub(pattern, r'\g<1>"' + value + r'"', text, count=1)
    sec_pattern = r'(\[\s*' + re.escape(section) + r'\s*\][^\r\n]*[\r\n]+)'
    if re.search(sec_pattern, text):
        return re.sub(sec_pattern, r'\g<1>' + key + r' = "' + value + r'"\n', text, count=1)
    return text.rstrip() + f'\n\n[{section}]\n{key} = "{value}"\n'


def _run_hostutils_dedicated(
    base: Path,
    pkg_toml_path: Path,
    *,
    auto_patch: bool = False,
    dry_run: bool = False,
    set_versions: dict[str, str] | None = None,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> int:
    """Sincroniza una librería dedicada donde todo el repositorio es un paquete."""
    import core.compiler
    from core.library import LibraryError, compute_library_signature, pack_library

    raw_text = pkg_toml_path.read_text(encoding='utf-8')
    try:
        pkg_data = tomllib.loads(raw_text)
    except Exception as exc:
        raise HostingError(f'Error al leer {pkg_toml_path}: {exc}') from exc

    pkg_section = pkg_data.get('package', {}) if isinstance(pkg_data.get('package'), dict) else {}
    author_section = pkg_data.get('author', {}) if isinstance(pkg_data.get('author'), dict) else {}

    name = str(pkg_section.get('name') or base.name)
    current_version = validate_semver(
        str(pkg_section.get('version') or '1.0.0'),
        context=f'Versión de {name}',
    )
    kind = str(pkg_section.get('kind') or 'librería')
    format_name = str(pkg_section.get('format') or 'lib1')
    if format_name != 'lib1':
        raise HostingError(
            f'Central solo admite librerías lib1; el paquete {name} declara {format_name!r}.'
        )
    description = str(pkg_section.get('description') or f'Biblioteca {name} para Bagron')
    license_name = str(pkg_section.get('license') or 'MIT')
    author = str(author_section.get('name') or 'Discentra Community')
    declared_sig = str(author_section.get('signature') or '')

    build_dir = base / 'build'
    central_dir = base / 'discentra_central'

    if not dry_run:
        build_dir.mkdir(parents=True, exist_ok=True)
        central_dir.mkdir(parents=True, exist_ok=True)

    file_name = f'{name}.lib'
    artifact_path = build_dir / file_name

    # Si el artefacto no existe, dry-run empaqueta únicamente en un temporal.
    if not artifact_path.is_file():
        if format_name == 'lib1':
            print_fn(f'  [hostutils] Empaquetando librería dedicada {name} en build/{file_name}...')
            try:
                packer = pack_library
                if dry_run:
                    with tempfile.TemporaryDirectory(prefix='bagron-hostutils-') as temp_dir:
                        temporary_root = Path(temp_dir) / 'source'
                        shutil.copytree(
                            base,
                            temporary_root,
                            ignore=shutil.ignore_patterns(
                                'build', 'log', 'discentra_central', '.git',
                                '.bagron-cache', '__pycache__',
                            ),
                        )
                        temporary_artifact = Path(temp_dir) / file_name
                        packer(temporary_root, temporary_artifact, name=name, version=current_version)
                        art = _inspect_hosted_artifact(temporary_artifact)
                else:
                    _pack_library_atomically(
                        packer,
                        base,
                        artifact_path,
                        name=name,
                        version=current_version,
                    )
                    art = _inspect_hosted_artifact(artifact_path)
            except Exception as exc:
                raise HostingError(
                    f'El artefacto {file_name} no existe en {build_dir} y la compilación falló:\n{exc}'
                ) from exc
        else:
            raise HostingError(f'No se encontró el artefacto {artifact_path.name} en {build_dir}')
    else:
        art = _inspect_hosted_artifact(artifact_path)
    curr_sha = str(art['sha256'])
    curr_size = int(art['size_bytes'])
    source_sha = str(art['source_sha'])

    manifest_toml_path = central_dir / 'manifest.toml'
    packages_toml_path = central_dir / 'packages.toml'

    prev_sha = None
    prev_sig = None
    if manifest_toml_path.is_file():
        try:
            man_content = tomllib.loads(manifest_toml_path.read_text(encoding='utf-8'))
            for p in man_content.get('packages', []):
                if isinstance(p, dict) and p.get('name') == name:
                    prev_sha = str(p.get('sha256', ''))
                    prev_sig = str(p.get('signature', ''))
                    break
        except Exception:
            pass

    is_modified = (prev_sha is None) or (prev_sha != curr_sha)
    set_versions = set_versions or {}

    print_fn(f'Auditando repositorio dedicado para paquete {name}...')

    if not is_modified:
        print_fn(f'  [hostutils] {name}: sin cambios (SHA256: {curr_sha[:16]}...)')
        version = current_version
    else:
        if prev_sha is None:
            version = validate_semver(
                set_versions[name] if name in set_versions else current_version,
                context=f'Versión de {name}',
            )
            if name in set_versions:
                print_fn(f'  [hostutils] {name}: versión fijada a {version}')
        else:
            version = _select_changed_version(
                name,
                current_version,
                bump_semver_patch(current_version),
                auto_patch=auto_patch,
                set_versions=set_versions,
                input_fn=input_fn,
                print_fn=print_fn,
            )
    if version != current_version and format_name == 'lib1':
        try:
            packer = pack_library
            if dry_run:
                with tempfile.TemporaryDirectory(prefix='bagron-hostutils-preview-') as temp_dir:
                    temporary_root = Path(temp_dir) / 'source'
                    shutil.copytree(
                        base,
                        temporary_root,
                        ignore=shutil.ignore_patterns(
                            'build', 'log', 'discentra_central', '.git',
                            '.bagron-cache', '__pycache__',
                        ),
                    )
                    temporary_artifact = Path(temp_dir) / file_name
                    packer(temporary_root, temporary_artifact, name=name, version=version)
                    art = _inspect_hosted_artifact(temporary_artifact)
            else:
                _pack_library_atomically(
                    packer,
                    base,
                    artifact_path,
                    name=name,
                    version=version,
                )
                art = _inspect_hosted_artifact(artifact_path)
            curr_sha = str(art['sha256'])
            curr_size = int(art['size_bytes'])
            source_sha = str(art['source_sha'])
        except Exception as error:
            raise HostingError(
                f'No se pudo regenerar el artefacto {artifact_path.name}: {error}'
            ) from error

    if format_name == 'lib1':
        art = _align_artifact_version(
            artifact_path,
            art,
            name=name,
            version=version,
            dry_run=dry_run,
        )
        curr_sha = str(art['sha256'])
        curr_size = int(art['size_bytes'])
        source_sha = str(art['source_sha'])

    if is_modified or version != current_version:
        try:
            signature, _ = compute_library_signature(base, author=author, name=name, version=version)
        except LibraryError:
            signature = compute_author_signature(author, name, version, source_sha)
    else:
        signature = prev_sig or declared_sig or compute_author_signature(author, name, version, source_sha)

    new_toml_text = _update_toml_field(raw_text, 'version', version, section='package')
    new_toml_text = _update_toml_field(new_toml_text, 'signature', signature, section='author')

    pkg_item = {
        'name': name,
        'file': file_name,
        'version': version,
        'kind': kind,
        'format': format_name,
        'description': description,
        'license': license_name,
        'sha256': curr_sha,
        'size_bytes': curr_size,
        'signature': signature,
    }

    repo_meta = {
        'name': name,
        'description': description,
        'author': author,
    }
    man_meta = {
        'format': 'bagron-manifest@1',
        'hash_algorithm': 'sha256',
        'author': author,
    }

    packages_toml_content = render_packages_toml(repo_meta, [pkg_item])
    manifest_toml_content = render_manifest_toml(man_meta, [pkg_item])

    if dry_run:
        print_fn('\n[DRY RUN] Sincronización dedicada que se habría aplicado:')
        print_fn(f'  Paquete    : {name} v{version}')
        print_fn(f'  SHA256     : {curr_sha}')
        print_fn(f'  Firma      : {signature}')
        return 0

    _atomic_write_texts([
        (pkg_toml_path, new_toml_text),
        (packages_toml_path, packages_toml_content),
        (manifest_toml_path, manifest_toml_content),
    ])

    print_fn(f'\nSincronización completada exitosamente (librería dedicada):')
    print_fn(f'  Paquete sincronizado : {name} v{version}')
    print_fn(f'  Artefacto verificado : {artifact_path}')
    print_fn(f'  Actualizado: {pkg_toml_path}')
    print_fn(f'  Actualizado: {packages_toml_path}')
    print_fn(f'  Actualizado: {manifest_toml_path}')

    return 0


def run_hostutils(
    target_dir: str | Path = '.',
    *,
    auto_patch: bool = False,
    dry_run: bool = False,
    set_versions: dict[str, str] | None = None,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> int:
    """Ejecuta la sincronización de artefactos y generación de manifiestos en el repositorio."""
    base = Path(target_dir).resolve()
    validated_set_versions: dict[str, str] = {}
    for package_name, package_version in (set_versions or {}).items():
        if not isinstance(package_name, str):
            raise HostingError('El nombre de paquete de --set-version debe ser texto.')
        validated_set_versions[package_name] = validate_semver(
            package_version,
            context=f'Versión fijada de {package_name}',
        )
    set_versions = validated_set_versions
    pkg_toml_path = base / 'package.toml'
    if pkg_toml_path.is_file():
        return _run_hostutils_dedicated(
            base,
            pkg_toml_path,
            auto_patch=auto_patch,
            dry_run=dry_run,
            set_versions=set_versions,
            input_fn=input_fn,
            print_fn=print_fn,
        )

    build_dir = base / 'build'
    central_dir = base / 'discentra_central'

    if not build_dir.is_dir():
        raise HostingError(f'Directorio build/ no encontrado en {base}')
    if not central_dir.is_dir():
        raise HostingError(f'Directorio discentra_central/ no encontrado en {base}')

    manifest_json_path = central_dir / 'manifest.json'
    manifest_json_data = load_manifest_json(manifest_json_path)

    json_repo = manifest_json_data.get('repository', {}) if isinstance(manifest_json_data.get('repository'), dict) else {}
    json_packages = manifest_json_data.get('packages', {}) if isinstance(manifest_json_data.get('packages'), dict) else {}

    # Leer TOMLs existentes si están presentes
    packages_toml_path = central_dir / 'packages.toml'
    manifest_toml_path = central_dir / 'manifest.toml'

    existing_packages_toml: dict[str, object] = {}
    existing_manifest_toml: dict[str, object] = {}

    if packages_toml_path.is_file():
        try:
            existing_packages_toml = tomllib.loads(packages_toml_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    if manifest_toml_path.is_file():
        try:
            existing_manifest_toml = tomllib.loads(manifest_toml_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    existing_pkg_map: dict[str, dict[str, object]] = {}
    for item in existing_packages_toml.get('packages', []):
        if isinstance(item, dict) and 'name' in item:
            existing_pkg_map[str(item['name'])] = item

    existing_man_map: dict[str, dict[str, object]] = {}
    for item in existing_manifest_toml.get('packages', []):
        if isinstance(item, dict) and 'name' in item:
            existing_man_map[str(item['name'])] = item

    author = (
        json_repo.get('author')
        or existing_manifest_toml.get('manifest', {}).get('author')
        or existing_packages_toml.get('repository', {}).get('author')
        or 'Discentra Community'
    )
    repo_name = (
        json_repo.get('name')
        or existing_packages_toml.get('repository', {}).get('name')
        or base.name
    )
    repo_desc = (
        json_repo.get('description')
        or existing_packages_toml.get('repository', {}).get('description')
        or 'Monorepo con la suite oficial de librerías y utilidades para Bagron'
    )

    # Escanear artefactos en build/
    artifacts: list[dict[str, object]] = []
    for file_path in sorted(build_dir.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() == '.lib':
            # Central publica únicamente contenedores de librería lib1.
            artifacts.append(_inspect_hosted_artifact(file_path))

    if not artifacts:
        print_fn('No se encontraron artefactos lib1 (.lib) en build/.')
        return 0

    print_fn(f'Auditando {len(artifacts)} artefacto(s) en build/...')
    final_packages: list[dict[str, object]] = []
    modified_count = 0
    unchanged_count = 0

    set_versions = set_versions or {}
    seen_names: set[str] = set()

    for art in artifacts:
        name = str(art['name'])
        if name in seen_names:
            raise HostingError(f'Hay más de un artefacto para el paquete {name!r} en build/.')
        seen_names.add(name)
        if art['format'] != 'lib1':
            raise HostingError(
                f'Central solo admite artefactos lib1; {art["file"]} es {art["format"]}.'
            )
        curr_sha = str(art['sha256'])
        curr_size = int(art['size_bytes'])
        curr_format = str(art['format'])
        curr_kind = str(art['kind'])
        source_sha = str(art['source_sha'])

        prev_man = existing_man_map.get(name)
        prev_pkg = existing_pkg_map.get(name)
        json_pkg = json_packages.get(name, {}) if isinstance(json_packages.get(name), dict) else {}

        description = (
            json_pkg.get('description')
            or (prev_pkg.get('description') if prev_pkg else None)
            or f'Paquete {name} para Bagron'
        )
        license_name = (
            json_pkg.get('license')
            or (prev_pkg.get('license') if prev_pkg else None)
            or 'MIT'
        )
        kind = (
            json_pkg.get('kind')
            or curr_kind
            or (prev_pkg.get('kind') if prev_pkg else None)
            or 'librería'
        )

        prev_sha = str(prev_man['sha256']) if prev_man and 'sha256' in prev_man else None
        prev_version = str(prev_pkg['version']) if prev_pkg and 'version' in prev_pkg else '1.0.0'

        is_modified = (prev_sha is None) or (prev_sha != curr_sha)

        if not is_modified:
            # Sin cambios
            unchanged_count += 1
            version = validate_semver(prev_version, context=f'Versión de {name}')
            signature = str(prev_man.get('signature', '')) if prev_man else compute_author_signature(author, name, version, source_sha)
        else:
            # Modificado o nuevo
            modified_count += 1
            if prev_sha is None:
                version = validate_semver(
                    set_versions[name]
                    if name in set_versions
                    else (art.get('internal_version') or '1.0.0'),
                    context=f'Versión de {name}',
                )
                if name in set_versions:
                    print_fn(f'  [hostutils] {name}: versión fijada a {version}')
            else:
                version = _select_changed_version(
                    name,
                    validate_semver(prev_version, context=f'Versión de {name}'),
                    bump_semver_patch(prev_version),
                    auto_patch=auto_patch,
                    set_versions=set_versions,
                    input_fn=input_fn,
                    print_fn=print_fn,
                )

            aligned_art = _align_artifact_version(
                Path(art['path']),
                art,
                name=name,
                version=version,
                dry_run=dry_run,
            )
            curr_sha = str(aligned_art['sha256'])
            curr_size = int(aligned_art['size_bytes'])
            source_sha = str(aligned_art['source_sha'])
            art = aligned_art
            signature = compute_author_signature(author, name, version, source_sha)

        if not is_modified:
            aligned_art = _align_artifact_version(
                Path(art['path']),
                art,
                name=name,
                version=version,
                dry_run=dry_run,
            )
            if aligned_art is not art:
                curr_sha = str(aligned_art['sha256'])
                curr_size = int(aligned_art['size_bytes'])
                source_sha = str(aligned_art['source_sha'])
                art = aligned_art

        final_packages.append({
            'name': name,
            'file': art['file'],
            'version': version,
            'kind': kind,
            'format': curr_format,
            'description': description,
            'license': license_name,
            'sha256': curr_sha,
            'size_bytes': curr_size,
            'signature': signature,
        })

    # Si no existe manifest.json, podemos generarlo como base para futuras descripciones
    if not manifest_json_path.is_file():
        default_manifest_json = {
            'repository': {
                'name': repo_name,
                'description': repo_desc,
                'author': author,
            },
            'packages': {
                pkg['name']: {
                    'description': pkg['description'],
                    'license': pkg['license'],
                    'kind': pkg['kind'],
                }
                for pkg in final_packages
            },
        }
        if not dry_run:
            _atomic_write_text(
                manifest_json_path,
                json.dumps(default_manifest_json, indent=2, ensure_ascii=False) + '\n',
            )
            print_fn(f'Generado catálogo base: {manifest_json_path.name}')

    repo_meta = {
        'name': repo_name,
        'description': repo_desc,
        'author': author,
    }
    man_meta = {
        'format': 'bagron-manifest@1',
        'hash_algorithm': 'sha256',
        'author': author,
    }

    packages_toml_content = render_packages_toml(repo_meta, final_packages)
    manifest_toml_content = render_manifest_toml(man_meta, final_packages)

    if dry_run:
        print_fn('\n[DRY RUN] Manifiestos que se habrían actualizado:')
        print_fn(f'  Modificados: {modified_count}')
        print_fn(f'  Sin cambios: {unchanged_count}')
        return 0

    _atomic_write_texts([
        (packages_toml_path, packages_toml_content),
        (manifest_toml_path, manifest_toml_content),
    ])

    print_fn(f'\nSincronización completada exitosamente:')
    print_fn(f'  Artefactos analizados : {len(final_packages)}')
    print_fn(f'  Paquetes actualizados : {modified_count}')
    print_fn(f'  Paquetes sin cambios  : {unchanged_count}')
    print_fn(f'  Actualizado: {packages_toml_path}')
    print_fn(f'  Actualizado: {manifest_toml_path}')

    return 0

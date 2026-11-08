"""Cliente de registro oficial para descarga e instalación de paquetes Bagron desde Central.

Proporciona resolución remota de versiones, descarga segura con Client ID y Public ID,
verificación criptográfica de checksums SHA-256 e instalación directa en libs/.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from typing import Callable


DEFAULT_REGISTRY_URL = os.environ.get('BAGRON_REGISTRY_URL', 'https://central.discentra.net').rstrip('/')
DEFAULT_CLIENT_ID = os.environ.get('BAGRON_CLIENT_ID', 'bagron-cli')
DEFAULT_PUBLIC_ID = os.environ.get('BAGRON_PUBLIC_ID', 'bg_pub_official_2026')
_PACKAGE_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
_SHA256_RE = re.compile(r'^[0-9a-fA-F]{64}$')
_MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024
_MAX_SOURCE_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
_MAX_SOURCE_ENTRIES = 20_000
_MAX_SEARCH_RESULTS = 10_000
_MAX_SEARCH_RESPONSE_BYTES = 16 * 1024 * 1024


class RegistryError(RuntimeError):
    """Error base de comunicación con el registro Central."""


class PackageNotFoundError(RegistryError):
    """El paquete o versión solicitada no existe en Central."""


class IntegrityError(RegistryError):
    """El checksum del paquete descargado no coincide con el registrado."""


class _CentralRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep HTTPS on every redirect and do not leak Central credentials."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_https_url(newurl, field='La redirección de Central')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None
        old_host = urllib.parse.urlparse(req.full_url).netloc.lower()
        new_host = urllib.parse.urlparse(newurl).netloc.lower()
        if old_host != new_host:
            for header in ('X-Central-Client-Id', 'X-Central-Public-Id', 'Accept'):
                redirected.headers.pop(header, None)
        return redirected


_CENTRAL_OPENER = urllib.request.build_opener(_CentralRedirectHandler())


def _open_url(request: urllib.request.Request, *, timeout: int):
    """Open an HTTPS request through the redirect policy used by Central."""
    return _CENTRAL_OPENER.open(request, timeout=timeout)


def _read_limited(response, *, limit: int, context: str) -> bytes:
    """Read a response without allowing unbounded memory growth."""
    header_value = getattr(response, 'headers', {}).get('Content-Length')
    if header_value:
        try:
            if int(header_value) > limit:
                raise RegistryError(f'{context} supera el limite de tamaño permitido.')
        except ValueError:
            raise RegistryError(f'{context} tiene un Content-Length invalido.')
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(64 * 1024, limit - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise RegistryError(f'{context} supera el limite de tamaño permitido.')
        chunks.append(chunk)
    return b''.join(chunks)


def _validate_source_zip(data: bytes) -> set[str]:
    """Validate source archive names, links, duplicates and expansion limits."""
    from core.library import LibraryError, _safe_member

    try:
        archive = zipfile.ZipFile(io.BytesIO(data), 'r')
    except Exception as error:
        raise RegistryError(f'El ZIP fuente no es valido: {error}') from error
    try:
        infos = archive.infolist()
        if len(infos) > _MAX_SOURCE_ENTRIES:
            raise RegistryError('El ZIP fuente contiene demasiadas entradas.')
        members: set[str] = set()
        member_keys: set[str] = set()
        total = 0
        for info in infos:
            try:
                safe = _safe_member(info.filename).as_posix()
            except LibraryError as error:
                raise RegistryError(f'La ruta del ZIP fuente no es segura: {info.filename!r}') from error
            if info.is_dir() or info.filename.endswith('/'):
                continue
            if info.flag_bits & 0x1:
                raise RegistryError(f'El ZIP fuente contiene una entrada cifrada: {info.filename!r}')
            if stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF):
                raise RegistryError(f'El ZIP fuente contiene un enlace simbólico: {info.filename!r}')
            if safe.casefold() in member_keys:
                raise RegistryError(f'El ZIP fuente contiene entradas duplicadas: {info.filename!r}')
            total += info.file_size
            if total > _MAX_SOURCE_UNCOMPRESSED_BYTES:
                raise RegistryError('El ZIP fuente supera el limite descomprimido permitido.')
            members.add(safe)
            member_keys.add(safe.casefold())
        return members
    finally:
        archive.close()


def _validate_package_name(value: str, *, field: str = 'nombre de paquete') -> str:
    """Valida un identificador que también se usará como nombre de archivo local."""
    if not isinstance(value, str):
        raise RegistryError(f'{field.capitalize()} inválido: se esperaba texto.')
    name = value.strip()
    if not _PACKAGE_NAME_RE.fullmatch(name) or name in {'.', '..'}:
        raise RegistryError(
            f"{field.capitalize()} inválido: {value!r}. "
            'Solo se permiten letras, números, punto, guion y guion bajo.'
        )
    return name


def _validate_https_url(value: str, *, field: str) -> str:
    """Rechaza destinos HTTPS ambiguos o que puedan filtrar credenciales."""
    url = value.strip()
    if not url or any(character.isspace() for character in url):
        raise RegistryError(f'{field} debe usar una URL HTTPS absoluta.')
    parsed = urllib.parse.urlparse(url)
    try:
        hostname = parsed.hostname
        parsed.port
    except ValueError as error:
        raise RegistryError(f'{field} contiene un puerto invalido.') from error
    if (
        parsed.scheme.lower() != 'https'
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise RegistryError(f'{field} debe usar una URL HTTPS absoluta.')
    return url


def _url_origin(value: str) -> str:
    """Return a canonical host-and-port origin after HTTPS validation."""
    parsed = urllib.parse.urlparse(
        value if '://' in value else f'https://{value}'
    )
    hostname = (parsed.hostname or '').lower().rstrip('.')
    port = parsed.port or 443
    return f'{hostname}:{port}'


def _reject_symlink_ancestors(path: Path) -> None:
    """Keep registry writes inside a real directory tree."""
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise RegistryError(f'La ruta de instalación contiene un enlace simbólico: {candidate}')


def _normalise_checksum(value: str | None, *, required: bool = True) -> str | None:
    """Normaliza y valida un checksum SHA-256 expresado con o sin prefijo."""
    if value is None or not value.strip():
        if required:
            raise IntegrityError('Central no proporcionó un checksum SHA-256 verificable.')
        return None

    checksum = value.strip().lower()
    if checksum.startswith('sha256:'):
        checksum = checksum.split(':', 1)[1].strip()
    if not _SHA256_RE.fullmatch(checksum):
        raise IntegrityError('El checksum proporcionado por Central no es un SHA-256 válido.')
    return checksum


def _get_headers(client_id: str = DEFAULT_CLIENT_ID, public_id: str = DEFAULT_PUBLIC_ID) -> dict[str, str]:
    """Genera las cabeceras requeridas para consultar y descargar desde Central."""
    for value, field in ((client_id, 'Client ID'), (public_id, 'Public ID')):
        if not isinstance(value, str) or not value.strip() or any(
            character in value for character in '\r\n'
        ):
            raise RegistryError(f'El {field} de Central no es valido.')
    return {
        'User-Agent': 'Bagron-CLI/Official',
        'Accept': 'application/json',
        'X-Central-Client-Id': client_id,
        'X-Central-Public-Id': public_id,
    }


def resolve_package(
    name: str,
    version: str | None = None,
    *,
    registry_url: str = DEFAULT_REGISTRY_URL,
    client_id: str = DEFAULT_CLIENT_ID,
    public_id: str = DEFAULT_PUBLIC_ID,
    timeout: int = 15,
) -> dict[str, object]:
    """Consulta la API de Central para comprobar si existe un paquete y resolver su metadata."""
    base_url = _validate_https_url(registry_url, field='El registro Central')
    package_name = _validate_package_name(name)
    enc_name = urllib.parse.quote(package_name, safe='')
    endpoint = f'{base_url}/api/bagron/packages/{enc_name}'
    if version and version.strip().lower() != 'latest':
        enc_ver = urllib.parse.quote(version.strip(), safe='')
        endpoint = f'{endpoint}/{enc_ver}'

    req = urllib.request.Request(endpoint, headers=_get_headers(client_id, public_id))

    try:
        with _open_url(req, timeout=timeout) as response:
            payload = json.loads(_read_limited(
                response,
                limit=16 * 1024 * 1024,
                context='La respuesta de Central',
            ).decode('utf-8'))
            if not isinstance(payload, dict) or not payload.get('exists') or not isinstance(payload.get('package'), dict):
                raise PackageNotFoundError(f"El paquete '{name}' no existe en Central.")
            package = payload['package']
            returned_name = _validate_package_name(
                package.get('name', ''),
                field='Nombre devuelto por Central',
            )
            if returned_name != package_name:
                raise RegistryError(
                    f"Central devolvió el paquete {returned_name!r} para la solicitud {package_name!r}."
                )
            if version and version.strip().lower() != 'latest':
                returned_version = package.get('version', '')
                if not isinstance(returned_version, str):
                    raise RegistryError('Central devolvió una versión no textual.')
                returned_version = returned_version.strip()
                if returned_version != version.strip():
                    raise RegistryError(
                        f"Central devolvió la versión {returned_version!r}; se solicitó {version!r}."
                    )
            return package
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise PackageNotFoundError(
                f"El paquete '{name}'{' v' + version if version else ''} no existe en Central."
            ) from error
        raise RegistryError(f'Error del servidor Central (HTTP {error.code}): {error.reason}') from error
    except urllib.error.URLError as error:
        raise RegistryError(f'No se pudo conectar con el registro Central ({registry_url}): {error.reason}') from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RegistryError(f'Respuesta no válida del registro Central: {error}') from error


def download_package_artifact(
    download_url: str,
    *,
    raw_fallback_url: str | None = None,
    expected_checksum: str | None = None,
    allow_unverified: bool = False,
    client_id: str = DEFAULT_CLIENT_ID,
    public_id: str = DEFAULT_PUBLIC_ID,
    credential_origin: str | None = None,
    timeout: int = 30,
) -> bytes:
    """Descarga los bytes del artefacto desde Central con credenciales y valida su checksum."""
    download_url = _validate_https_url(download_url, field='La URL de descarga')
    if raw_fallback_url:
        raw_fallback_url = _validate_https_url(raw_fallback_url, field='La URL de fallback')
    clean_expected = _normalise_checksum(expected_checksum, required=not allow_unverified)

    headers = _get_headers(client_id, public_id)
    headers['Accept'] = '*/*'
    if credential_origin is None or _url_origin(download_url) != _url_origin(credential_origin):
        headers.pop('X-Central-Client-Id', None)
        headers.pop('X-Central-Public-Id', None)

    req = urllib.request.Request(download_url, headers=headers)
    data: bytes | None = None

    try:
        with _open_url(req, timeout=timeout) as response:
            data = _read_limited(
                response,
                limit=_MAX_DOWNLOAD_BYTES,
                context='El artefacto descargado',
            )
    except RegistryError:
        raise
    except (urllib.error.URLError, OSError) as exc:
        if raw_fallback_url:
            try:
                raw_req = urllib.request.Request(raw_fallback_url, headers={'User-Agent': headers['User-Agent']})
                with _open_url(raw_req, timeout=timeout) as fallback_res:
                    data = _read_limited(
                        fallback_res,
                        limit=_MAX_DOWNLOAD_BYTES,
                        context='El artefacto de fallback',
                    )
            except Exception:
                raise RegistryError(f'Error al descargar artefacto desde {download_url}: {exc}') from exc
        else:
            raise RegistryError(f'Error al descargar artefacto desde {download_url}: {exc}') from exc

    if not data:
        raise RegistryError('El artefacto descargado está vacío.')

    # Validación de integridad SHA-256
    if clean_expected:
        actual_sha = hashlib.sha256(data).hexdigest().lower()
        if actual_sha != clean_expected:
            raise IntegrityError(
                f'Error de integridad: el hash SHA-256 descargado ({actual_sha}) '
                f'no coincide con el esperado de Central ({clean_expected}).'
            )

    return data


def install_package(
    package_spec: str,
    version_arg: str | None = None,
    *,
    target_dir: str | Path = 'libs',
    registry_url: str = DEFAULT_REGISTRY_URL,
    client_id: str = DEFAULT_CLIENT_ID,
    public_id: str = DEFAULT_PUBLIC_ID,
    allow_unverified: bool = False,
    lockfile_path: str | Path | None = None,
    print_fn: Callable[[str], None] = print,
) -> Path:
    """Resuelve, descarga e instala una librería en el directorio local libs/."""
    # Soporta sintaxis nombre@version, nombre==version o argumentos separados
    name = package_spec.strip()
    version = version_arg.strip() if version_arg else None

    if '==' in name and version is None:
        parts = name.split('==', 1)
        name = parts[0].strip()
        version = parts[1].strip()
    elif '@' in name and version is None:
        parts = name.split('@', 1)
        name = parts[0].strip()
        version = parts[1].strip()

    _validate_package_name(name, field='Nombre solicitado')

    raw_dest_folder = Path(target_dir)
    _reject_symlink_ancestors(raw_dest_folder)
    try:
        raw_dest_folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise RegistryError(
            f'No se pudo crear el directorio de instalación de paquetes: {raw_dest_folder}'
        ) from error
    if raw_dest_folder.is_symlink() or not raw_dest_folder.is_dir():
        raise RegistryError(
            f'El directorio de instalación de paquetes no es seguro: {raw_dest_folder}'
        )
    dest_folder = raw_dest_folder.resolve()
    _reject_symlink_ancestors(dest_folder)
    lock_path = Path(lockfile_path) if lockfile_path is not None else None

    print_fn(f"Buscando '{name}'{' v' + version if version else ''} en Central ({registry_url})...")
    package_info = resolve_package(
        name,
        version,
        registry_url=registry_url,
        client_id=client_id,
        public_id=public_id,
    )
    registry_origin = _url_origin(
        _validate_https_url(registry_url, field='El registro Central')
    )

    resolved_name = _validate_package_name(
        package_info.get('name', name),
        field='Nombre devuelto por Central',
    )
    if resolved_name != name:
        raise RegistryError(
            f"Central devolvió el paquete {resolved_name!r}; se solicitó {name!r}."
        )
    resolved_version = package_info.get('version', '1.0.0')
    if not isinstance(resolved_version, str):
        raise RegistryError('Central devolvió una versión no textual.')
    resolved_version = resolved_version.strip()
    package_format = package_info.get('package_format', 'lib1')
    if not isinstance(package_format, str):
        raise RegistryError('Central devolvió un formato de paquete no textual.')
    if package_format not in {'lib1', 'lib2'}:
        raise RegistryError(
            f"Central devolvió un formato de paquete no soportado: {package_format!r}."
        )
    if not resolved_version.strip():
        raise RegistryError('Central no devolvió una versión de paquete válida.')
    if version and version.lower() != 'latest' and resolved_version != version:
        raise RegistryError(
            f"Central devolvió la versión {resolved_version!r}; se solicitó {version!r}."
        )
    expected_checksum = package_info.get('artifact_checksum')
    if expected_checksum is not None and not isinstance(expected_checksum, str):
        raise RegistryError('Central devolvió un checksum no textual.')
    expected_checksum = expected_checksum or None
    download_url = package_info.get('download_url', '')
    if not isinstance(download_url, str):
        raise RegistryError('Central devolvió una URL de descarga no textual.')
    raw_fallback = package_info.get('raw_github_url', '')
    if raw_fallback is not None and not isinstance(raw_fallback, str):
        raise RegistryError('Central devolvió una URL de fallback no textual.')
    raw_fallback = raw_fallback or None

    if not download_url and not raw_fallback:
        raise RegistryError(f"El paquete '{resolved_name}' no tiene una URL de descarga configurada en Central.")

    download_target = download_url or raw_fallback

    print_fn(f"Descargando {resolved_name} v{resolved_version} ({package_format})...")
    data = download_package_artifact(
        download_target,
        raw_fallback_url=raw_fallback,
        expected_checksum=expected_checksum,
        allow_unverified=allow_unverified,
        client_id=client_id,
        public_id=public_id,
        credential_origin=registry_origin,
    )
    minimum_tuf_version = None
    if lock_path is not None:
        from core.lockfile import LockfileError, load_lockfile
        try:
            current_lock = load_lockfile(lock_path)
        except LockfileError as error:
            raise RegistryError(f'No se pudo leer bagron.lock: {error}') from error
        if isinstance(current_lock, dict):
            current_central_tuf = current_lock.get('central_tuf')
            if isinstance(current_central_tuf, dict):
                minimum_tuf_version = current_central_tuf.get('targets_version')

    from core.signing import (
        CentralSignatureError,
        central_metadata_version,
        verify_central_artifact,
    )
    tuf_version = None
    try:
        verify_central_artifact(
            package_info,
            data,
            resolved_name=resolved_name,
            resolved_version=resolved_version,
            package_format=package_format,
            require=os.environ.get('BAGRON_REQUIRE_CENTRAL_SIGNATURES', '').strip() == '1',
            minimum_version=minimum_tuf_version,
        )
        tuf_version = central_metadata_version(package_info)
    except CentralSignatureError as error:
        raise RegistryError(f'La firma de Central no es valida: {error}') from error

    if not dest_folder.is_dir() or dest_folder.is_symlink():
        raise RegistryError('El directorio de instalación no es seguro.')
    dest_file = dest_folder / f'{resolved_name}.lib'
    if dest_file.is_symlink() or dest_file.resolve().parent != dest_folder:
        raise RegistryError('La ruta de instalación escapa del directorio destino.')

    def publish_verified(data_to_publish: bytes) -> Path:
        """Validate the complete lib before atomically replacing the destination."""
        fd, temp_name = tempfile.mkstemp(
            prefix=f'.{dest_file.stem}.',
            suffix='.lib.tmp',
            dir=dest_folder,
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(data_to_publish)
                handle.flush()
                os.fsync(handle.fileno())
            # Import the compiler package first because library.py shares the
            # compiler mangling module and Python otherwise exposes a partial
            # core.library during package initialization.
            import core.compiler  # noqa: F401
            from core.library import LibraryError, verify_library
            try:
                package = verify_library(temp_path)
            except LibraryError as error:
                raise RegistryError(
                    f'El artefacto de {resolved_name} no es un paquete Bagron valido: {error}'
                ) from error
            actual_format = 'lib2' if package.library_version == 2 else 'lib1'
            if actual_format != package_format:
                raise RegistryError(
                    f'El formato declarado ({package_format}) no coincide con el artefacto ({actual_format}).'
                )
            if package.name != resolved_name or package.manifest.get('version') != resolved_version:
                raise RegistryError(
                    'El nombre o la version del paquete no coinciden con la metadata de Central.'
                )
            if lock_path is not None:
                from core.lockfile import LockfileError, update_lockfile
                manifest_dependencies = package.manifest.get('dependencies', [])
                central_dependencies = package_info.get('dependencies')
                if central_dependencies is not None:
                    if not isinstance(central_dependencies, list):
                        raise RegistryError('Central devolvió dependencies con un formato inválido.')
                    try:
                        central_names = sorted(
                            _validate_package_name(
                                item,
                                field='Nombre de dependencia de Central',
                            )
                            for item in central_dependencies
                        )
                        manifest_names = sorted(
                            _validate_package_name(
                                item,
                                field='Nombre de dependencia del paquete',
                            )
                            for item in manifest_dependencies
                        )
                    except RegistryError:
                        raise
                    if central_names != manifest_names:
                        raise RegistryError(
                            'Las dependencias de Central no coinciden con el manifiesto del paquete.'
                        )
                dependencies = manifest_dependencies
            if dest_file.is_symlink():
                raise RegistryError('El destino de instalación es un enlace simbólico.')
            previous_file: Path | None = None
            destination_replaced = False
            try:
                if dest_file.exists() or dest_file.is_symlink():
                    fd, previous_name = tempfile.mkstemp(
                        prefix=f'.{dest_file.stem}.previous.',
                        suffix='.lib.tmp',
                        dir=dest_folder,
                    )
                    os.close(fd)
                    previous_file = Path(previous_name)
                    previous_file.unlink(missing_ok=True)
                    os.replace(dest_file, previous_file)
                os.replace(temp_path, dest_file)
                destination_replaced = True
                if lock_path is not None:
                    try:
                        update_lockfile(
                            lock_path,
                            name=resolved_name,
                            version=resolved_version,
                            source=download_target,
                            package_format=package_format,
                            data=data_to_publish,
                            dependencies=[str(item) for item in dependencies],
                            tuf_version=tuf_version,
                        )
                    except LockfileError as error:
                        raise RegistryError(f'No se pudo actualizar bagron.lock: {error}') from error
            except Exception:
                if destination_replaced:
                    Path(dest_file).unlink(missing_ok=True)
                if previous_file is not None and (
                    previous_file.exists() or previous_file.is_symlink()
                ):
                    os.replace(previous_file, dest_file)
                raise
            finally:
                if previous_file is not None:
                    previous_file.unlink(missing_ok=True)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        return dest_file

    # Un archivo BGLIB siempre se valida antes de sustituir el instalado.
    if len(data) >= 8 and data[:8] == b'BGLIB1\0\0':
        publish_verified(data)
        print_fn(f"[ok] Paquete '{resolved_name}' v{resolved_version} instalado con exito en:")
        print_fn(f"  {dest_file}")
        return dest_file

    # Si es un ZIP proveniente de un repositorio dedicado
    if len(data) >= 4 and data[:4] == b'PK\x03\x04':
        from core.library import pack_library
        with tempfile.TemporaryDirectory() as temp_dir:
            extract_dir = Path(temp_dir) / 'extracted'
            _validate_source_zip(data)
            extract_dir.mkdir(parents=True, exist_ok=True)
            from core.library import LibraryError, _safe_member
            with zipfile.ZipFile(io.BytesIO(data), 'r') as archive:
                for info in archive.infolist():
                    if info.is_dir() or info.filename.endswith('/'):
                        continue
                    try:
                        safe = _safe_member(info.filename)
                    except LibraryError as error:
                        raise RegistryError(
                            f'La ruta del ZIP fuente no es segura: {info.filename!r}'
                        ) from error
                    output = (extract_dir / Path(*safe.parts)).resolve()
                    if extract_dir.resolve() not in output.parents:
                        raise RegistryError(f'La ruta del ZIP escapa de la raiz: {info.filename!r}')
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(archive.read(info))

            source_root = extract_dir
            subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
            if len(subdirs) == 1 and not (extract_dir / 'main.bg').is_file():
                source_root = subdirs[0]

            generated = Path(temp_dir) / f'{resolved_name}.lib'
            pack_library(source_root, generated, name=resolved_name, version=resolved_version)
            publish_verified(generated.read_bytes())
            print_fn(f"[ok] Paquete '{resolved_name}' v{resolved_version} empaquetado e instalado en:")
            print_fn(f"  {dest_file}")
            return dest_file

    raise RegistryError(
        f"El artefacto de {resolved_name} no es un contenedor BGLIB1 ni un ZIP fuente valido."
    )


def info_package(
    package_spec: str,
    version_arg: str | None = None,
    *,
    registry_url: str = DEFAULT_REGISTRY_URL,
    client_id: str = DEFAULT_CLIENT_ID,
    public_id: str = DEFAULT_PUBLIC_ID,
    print_fn: Callable[[str], None] = print,
) -> int:
    """Muestra la ficha técnica de un paquete publicado en Central."""
    name = package_spec.strip()
    version = version_arg.strip() if version_arg else None
    if '@' in name and version is None:
        parts = name.split('@', 1)
        name = parts[0].strip()
        version = parts[1].strip()

    package_info = resolve_package(
        name,
        version,
        registry_url=registry_url,
        client_id=client_id,
        public_id=public_id,
    )

    author = package_info.get('author', {}) if isinstance(package_info.get('author'), dict) else {}
    author_name = author.get('name') or package_info.get('author_name', 'Desconocido')

    print_fn(f"\nPaquete: {package_info.get('name')}")
    print_fn(f"Versión: {package_info.get('version')}")
    print_fn(f"Formato: {package_info.get('package_format', 'lib1')} ({package_info.get('kind', 'librería')})")
    print_fn(f"Licencia: {package_info.get('license', 'MIT')}")
    print_fn(f"Autor: {author_name}")
    print_fn(f"Descripción: {package_info.get('description', '')}")
    if package_info.get('artifact_checksum'):
        print_fn(f"SHA-256: {package_info.get('artifact_checksum')}")
    if package_info.get('signature'):
        print_fn(f"Firma: {package_info.get('signature')}")
    print_fn(f"Descargas: {package_info.get('downloads_count', 0)}")
    return 0


def search_packages(
    query: str = '',
    *,
    registry_url: str = DEFAULT_REGISTRY_URL,
    client_id: str = DEFAULT_CLIENT_ID,
    public_id: str = DEFAULT_PUBLIC_ID,
    print_fn: Callable[[str], None] = print,
) -> int:
    """Busca paquetes en el catálogo público de Central."""
    base_url = _validate_https_url(registry_url, field='El registro Central')
    endpoint = f'{base_url}/api/bagron/packages'
    if query.strip():
        endpoint = f'{endpoint}?search={urllib.parse.quote(query.strip(), safe="")}'

    req = urllib.request.Request(endpoint, headers=_get_headers(client_id, public_id))

    try:
        with _open_url(req, timeout=15) as response:
            raw_payload = _read_limited(
                response,
                limit=_MAX_SEARCH_RESPONSE_BYTES,
                context='La respuesta de búsqueda de Central',
            )
            payload = json.loads(raw_payload.decode('utf-8'))
            if not isinstance(payload, dict):
                raise RegistryError('La respuesta de búsqueda de Central no es un objeto JSON.')
            packages = payload.get('data') or payload.get('packages') or []
            if not isinstance(packages, list):
                raise RegistryError('La respuesta de búsqueda de Central no contiene una lista válida.')
            if len(packages) > _MAX_SEARCH_RESULTS:
                raise RegistryError('La respuesta de búsqueda de Central contiene demasiados resultados.')

            validated: list[tuple[str, str, str, str]] = []
            for package in packages:
                if not isinstance(package, dict):
                    raise RegistryError('La respuesta de búsqueda contiene una entrada inválida.')
                name = _validate_package_name(
                    package.get('name', ''),
                    field='Nombre devuelto por Central',
                )
                version = package.get('latest_version') or package.get('version') or ''
                if not isinstance(version, str) or not version.strip():
                    raise RegistryError(f'El paquete {name!r} no tiene una versión válida.')
                package_format = package.get('package_format', 'lib1')
                if package_format not in {'lib1', 'lib2'}:
                    raise RegistryError(
                        f'El paquete {name!r} tiene un formato inválido: {package_format!r}.'
                    )
                description = package.get('description', '')
                if not isinstance(description, str):
                    raise RegistryError(f'La descripción de {name!r} no es textual.')
                validated.append((name, version.strip(), package_format, description))

            if not validated:
                print_fn(f"No se encontraron paquetes para '{query}'.")
                return 0

            print_fn(f"\nPaquetes encontrados ({len(validated)}):")
            for name, version, package_format, description in validated:
                print_fn(f"  • {name} (v{version}, {package_format}) - {description}")
            print_fn('')
            return 0
    except RegistryError:
        raise
    except urllib.error.HTTPError as error:
        raise RegistryError(
            f'Error del servidor Central al buscar (HTTP {error.code}): {error.reason}'
        ) from error
    except urllib.error.URLError as error:
        raise RegistryError(f'No se pudo conectar con el registro Central: {error.reason}') from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RegistryError(f'Respuesta no válida del registro Central: {error}') from error

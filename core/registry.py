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
    name = value.strip()
    if not _PACKAGE_NAME_RE.fullmatch(name) or name in {'.', '..'}:
        raise RegistryError(
            f"{field.capitalize()} inválido: {value!r}. "
            'Solo se permiten letras, números, punto, guion y guion bajo.'
        )
    return name


def _validate_https_url(value: str, *, field: str) -> str:
    """Rechaza destinos de red que no sean HTTPS absolutos."""
    url = value.strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() != 'https' or not parsed.netloc:
        raise RegistryError(f'{field} debe usar una URL HTTPS absoluta.')
    return url


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
                str(package.get('name', '')),
                field='Nombre devuelto por Central',
            )
            if returned_name != package_name:
                raise RegistryError(
                    f"Central devolvió el paquete {returned_name!r} para la solicitud {package_name!r}."
                )
            if version and version.strip().lower() != 'latest':
                returned_version = str(package.get('version', '')).strip()
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
    except json.JSONDecodeError as error:
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
    if credential_origin is None or urllib.parse.urlparse(download_url).netloc.lower() != credential_origin.lower():
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

    dest_folder = Path(target_dir).resolve()
    lock_path = Path(lockfile_path).resolve() if lockfile_path is not None else None

    print_fn(f"Buscando '{name}'{' v' + version if version else ''} en Central ({registry_url})...")
    package_info = resolve_package(
        name,
        version,
        registry_url=registry_url,
        client_id=client_id,
        public_id=public_id,
        credential_origin=urllib.parse.urlparse(
            _validate_https_url(registry_url, field='El registro Central')
        ).netloc,
    )

    resolved_name = _validate_package_name(
        str(package_info.get('name', name)),
        field='Nombre devuelto por Central',
    )
    if resolved_name != name:
        raise RegistryError(
            f"Central devolvió el paquete {resolved_name!r}; se solicitó {name!r}."
        )
    resolved_version = str(package_info.get('version', '1.0.0'))
    package_format = str(package_info.get('package_format', 'lib1'))
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
    expected_checksum = str(package_info.get('artifact_checksum', '')) or None
    download_url = str(package_info.get('download_url', ''))
    raw_fallback = str(package_info.get('raw_github_url', '')) or None

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
    )
    from core.signing import CentralSignatureError, verify_central_artifact
    try:
        verify_central_artifact(
            package_info,
            data,
            resolved_name=resolved_name,
            resolved_version=resolved_version,
            package_format=package_format,
            require=os.environ.get('BAGRON_REQUIRE_CENTRAL_SIGNATURES', '').strip() == '1',
        )
    except CentralSignatureError as error:
        raise RegistryError(f'La firma de Central no es valida: {error}') from error

    dest_folder.mkdir(parents=True, exist_ok=True)
    dest_file = dest_folder / f'{resolved_name}.lib'
    if dest_file.resolve().parent != dest_folder:
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
            if package.name != resolved_name or str(package.manifest.get('version', '')) != resolved_version:
                raise RegistryError(
                    'El nombre o la version del paquete no coinciden con la metadata de Central.'
                )
            if lock_path is not None:
                from core.lockfile import LockfileError, update_lockfile
                raw_dependencies = package_info.get('dependencies', [])
                dependencies = raw_dependencies if isinstance(raw_dependencies, list) else []
                try:
                    update_lockfile(
                        lock_path,
                        name=resolved_name,
                        version=resolved_version,
                        source=download_target,
                        package_format=package_format,
                        data=data_to_publish,
                        dependencies=[str(item) for item in dependencies],
                    )
                except LockfileError as error:
                    raise RegistryError(f'No se pudo actualizar bagron.lock: {error}') from error
            os.replace(temp_path, dest_file)
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
        endpoint = f'{endpoint}?search={urllib.parse.quote(query.strip())}'

    req = urllib.request.Request(endpoint, headers=_get_headers(client_id, public_id))

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = json.loads(response.read().decode('utf-8'))
            packages = payload.get('data') or payload.get('packages') or []
            if not packages:
                print_fn(f"No se encontraron paquetes para '{query}'.")
                return 0

            print_fn(f"\nPaquetes encontrados ({len(packages)}):")
            for pkg in packages:
                name = pkg.get('name', '')
                ver = pkg.get('latest_version') or pkg.get('version', '')
                fmt = pkg.get('package_format', 'lib1')
                desc = pkg.get('description', '')
                print_fn(f"  • {name} (v{ver}, {fmt}) - {desc}")
            print_fn('')
            return 0
    except Exception as exc:
        raise RegistryError(f'Error al buscar paquetes en Central: {exc}') from exc

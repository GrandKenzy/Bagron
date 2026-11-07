"""Cliente de registro oficial para descarga e instalación de paquetes Bagron desde Central.

Proporciona resolución remota de versiones, descarga segura con Client ID y Public ID,
verificación criptográfica de checksums SHA-256 e instalación directa en libs/.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable


DEFAULT_REGISTRY_URL = os.environ.get('BAGRON_REGISTRY_URL', 'https://central.discentra.net').rstrip('/')
DEFAULT_CLIENT_ID = os.environ.get('BAGRON_CLIENT_ID', 'bagron-cli')
DEFAULT_PUBLIC_ID = os.environ.get('BAGRON_PUBLIC_ID', 'bg_pub_official_2026')
_PACKAGE_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
_SHA256_RE = re.compile(r'^[0-9a-fA-F]{64}$')


class RegistryError(RuntimeError):
    """Error base de comunicación con el registro Central."""


class PackageNotFoundError(RegistryError):
    """El paquete o versión solicitada no existe en Central."""


class IntegrityError(RegistryError):
    """El checksum del paquete descargado no coincide con el registrado."""


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


def _atomic_write_bytes(destination: Path, data: bytes) -> None:
    """Escribe un artefacto en el mismo directorio y lo publica atómicamente."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f'.{destination.stem}.',
        suffix='.tmp',
        dir=destination.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


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
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
            if not payload.get('exists') or 'package' not in payload:
                raise PackageNotFoundError(f"El paquete '{name}' no existe en Central.")
            return payload['package']
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
    timeout: int = 30,
) -> bytes:
    """Descarga los bytes del artefacto desde Central con credenciales y valida su checksum."""
    download_url = _validate_https_url(download_url, field='La URL de descarga')
    if raw_fallback_url:
        raw_fallback_url = _validate_https_url(raw_fallback_url, field='La URL de fallback')
    clean_expected = _normalise_checksum(expected_checksum, required=not allow_unverified)

    headers = _get_headers(client_id, public_id)
    headers['Accept'] = '*/*'

    req = urllib.request.Request(download_url, headers=headers)
    data: bytes | None = None

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read()
    except Exception as exc:
        if raw_fallback_url:
            try:
                raw_req = urllib.request.Request(raw_fallback_url, headers={'User-Agent': headers['User-Agent']})
                with urllib.request.urlopen(raw_req, timeout=timeout) as fallback_res:
                    data = fallback_res.read()
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

    print_fn(f"Buscando '{name}'{' v' + version if version else ''} en Central ({registry_url})...")
    package_info = resolve_package(
        name,
        version,
        registry_url=registry_url,
        client_id=client_id,
        public_id=public_id,
    )

    resolved_name = _validate_package_name(
        str(package_info.get('name', name)),
        field='Nombre devuelto por Central',
    )
    resolved_version = str(package_info.get('version', '1.0.0'))
    package_format = str(package_info.get('package_format', 'lib1'))
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

    dest_folder.mkdir(parents=True, exist_ok=True)
    dest_file = dest_folder / f'{resolved_name}.lib'
    if dest_file.resolve().parent != dest_folder:
        raise RegistryError('La ruta de instalación escapa del directorio destino.')

    # Si es un archivo empaquetado nativo Bagron (BGLIB1)
    if len(data) >= 8 and data[:6] == b'BGLIB1':
        _atomic_write_bytes(dest_file, data)
        print_fn(f"[ok] Paquete '{resolved_name}' v{resolved_version} instalado con exito en:")
        print_fn(f"  {dest_file}")
        return dest_file

    # Si es un ZIP proveniente de un repositorio dedicado
    if len(data) >= 4 and data[:4] == b'PK\x03\x04':
        from core.library import pack_library
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_zip = Path(temp_dir) / 'source.zip'
            temp_zip.write_bytes(data)
            extract_dir = Path(temp_dir) / 'extracted'
            shutil.unpack_archive(temp_zip, extract_dir)

            source_root = extract_dir
            subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
            if len(subdirs) == 1 and not (extract_dir / 'main.bg').is_file():
                source_root = subdirs[0]

            fd, temp_name = tempfile.mkstemp(
                prefix=f'.{dest_file.stem}.',
                suffix='.lib.tmp',
                dir=dest_folder,
            )
            temp_path = Path(temp_name)
            os.close(fd)
            try:
                pack_library(source_root, temp_path, name=resolved_name, version=resolved_version)
                os.replace(temp_path, dest_file)
            except Exception:
                temp_path.unlink(missing_ok=True)
                raise
            print_fn(f"[ok] Paquete '{resolved_name}' v{resolved_version} empaquetado e instalado en:")
            print_fn(f"  {dest_file}")
            return dest_file

    # Si es binario genérico
    _atomic_write_bytes(dest_file, data)
    print_fn(f"[ok] Artefacto guardado en:")
    print_fn(f"  {dest_file}")
    return dest_file


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

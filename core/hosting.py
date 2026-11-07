"""Herramientas de gestión y sincronización para repositorios de alojamiento Bagron (hostutils).

Automatiza la detección de artefactos modificados en build/, el cálculo de SHA-256,
tamaños y formatos, la solicitud interactiva de nuevas versiones y la generación
atómica de los manifiestos en discentra_central/ (packages.toml y manifest.toml).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import tomllib
from typing import Callable
import zipfile


class HostingError(RuntimeError):
    """Excepción para errores en operaciones de repositorios de alojamiento."""


_BGLIB_MAGIC = b'BGLIB1\0\0'
_BGLIB_HEADER = struct.Struct('<8sHHBBHQQ32s32s32s32s32s')


def bump_semver_patch(version: str) -> str:
    """Incrementa el componente patch de una versión SemVer (ej. 1.1.4 -> 1.1.5)."""
    parts = version.strip().split('.')
    if len(parts) >= 3 and parts[-1].isdigit():
        parts[-1] = str(int(parts[-1]) + 1)
        return '.'.join(parts)
    elif len(parts) == 2 and parts[-1].isdigit():
        return f'{parts[0]}.{parts[1]}.1'
    elif len(parts) == 1 and parts[0].isdigit():
        return f'{parts[0]}.0.1'
    return f'{version}.1'


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
    lines = [
        '# Configuración de integración de BagronLab con Central',
        '[repository]',
        f'name = "{repository.get("name", "bagronlab")}"',
        f'description = "{repository.get("description", "Monorepo con la suite oficial de librerías y utilidades para Bagron")}"',
        f'author = "{repository.get("author", "Discentra Community")}"',
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
        if file_path.suffix.lower() == '.lib' or not file_path.suffix:
            # Archivo de librería .lib o binario sin extensión
            artifacts.append(inspect_build_artifact(file_path))

    if not artifacts:
        print_fn('No se encontraron artefactos (.lib o binarios) en build/.')
        return 0

    print_fn(f'Auditando {len(artifacts)} artefacto(s) en build/...')
    final_packages: list[dict[str, object]] = []
    modified_count = 0
    unchanged_count = 0

    set_versions = set_versions or {}

    for art in artifacts:
        name = str(art['name'])
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
            version = prev_version
            signature = str(prev_man.get('signature', '')) if prev_man else compute_author_signature(author, name, version, source_sha)
        else:
            # Modificado o nuevo
            modified_count += 1
            suggested = bump_semver_patch(prev_version) if prev_sha is not None else (art.get('internal_version') or '1.0.0')

            if name in set_versions:
                version = set_versions[name]
                print_fn(f'  [hostutils] {name}: versión fijada a {version}')
            elif auto_patch:
                version = suggested
                print_fn(f'  [hostutils] {name}: cambio detectado -> auto-bump patch {prev_version} -> {version}')
            else:
                prompt_label = (
                    f'\n[hostutils] Paquete modificado detectado: {art["file"]}\n'
                    f'  Versión actual : {prev_version}\n'
                    f'  SHA256 anterior: {prev_sha or "(nuevo)"}\n'
                    f'  SHA256 nuevo   : {curr_sha}\n'
                    f'  Sugerencia     : {suggested}\n'
                    f"Nueva versión para '{name}' [{suggested}]: "
                )
                user_val = input_fn(prompt_label).strip()
                version = user_val if user_val else suggested

            signature = compute_author_signature(author, name, version, source_sha)

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
            manifest_json_path.write_text(
                json.dumps(default_manifest_json, indent=2, ensure_ascii=False) + '\n',
                encoding='utf-8',
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

    packages_toml_path.write_text(packages_toml_content, encoding='utf-8')
    manifest_toml_path.write_text(manifest_toml_content, encoding='utf-8')

    print_fn(f'\nSincronización completada exitosamente:')
    print_fn(f'  Artefactos analizados : {len(final_packages)}')
    print_fn(f'  Paquetes actualizados : {modified_count}')
    print_fn(f'  Paquetes sin cambios  : {unchanged_count}')
    print_fn(f'  Actualizado: {packages_toml_path}')
    print_fn(f'  Actualizado: {manifest_toml_path}')

    return 0

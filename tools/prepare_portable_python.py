"""Prepara un runtime portable de CPython para los instaladores de Bagron.

Las releases usan las distribuciones autocontenidas de
``astral-sh/python-build-standalone``. El artefacto ya incluye ``pip`` y se
puede ejecutar desde cualquier carpeta, por lo que Bagron no necesita
encontrar un Python instalado por el usuario.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request


PYTHON_STANDALONE_LATEST_URL = (
    'https://raw.githubusercontent.com/astral-sh/python-build-standalone/'
    'latest-release/latest-release.json'
)
PYTHON_STANDALONE_API_URL = (
    'https://api.github.com/repos/astral-sh/python-build-standalone/releases/tags/{tag}'
)
TARGET_TRIPLES = {
    'linux': 'x86_64-unknown-linux-gnu',
    'windows': 'x86_64-pc-windows-msvc',
}
DEFAULT_PYTHON_MINOR = '3.14'
USER_AGENT = 'Bagron-portable-python-builder'


def _request_json(url: str) -> dict:
    """Obtiene JSON desde una fuente remota con un User-Agent estable."""
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request) as response:
            payload = response.read()
    except urllib.error.URLError as error:
        raise RuntimeError(f'No se pudo consultar {url}: {error}') from error
    try:
        data = json.loads(payload.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f'La respuesta de {url} no contiene JSON válido.') from error
    if not isinstance(data, dict):
        raise RuntimeError(f'La respuesta de {url} no tiene un objeto JSON.')
    return data


def _resolve_release_tag(release_tag: str | None) -> str:
    """Resuelve la release de Python fijada o la última publicada."""
    if release_tag:
        return release_tag
    metadata = _request_json(PYTHON_STANDALONE_LATEST_URL)
    tag = metadata.get('tag')
    if not isinstance(tag, str) or not tag:
        raise RuntimeError('La metadata de python-build-standalone no tiene tag.')
    return tag


def _select_asset(
    assets: list[dict],
    *,
    python_minor: str,
    target: str,
) -> dict:
    """Selecciona un tarball GIL estándar, priorizando el variante stripped."""
    triple = TARGET_TRIPLES[target]
    pattern = re.compile(
        rf'^cpython-{re.escape(python_minor)}\.\d+\+[^-]+-'
        rf'{re.escape(triple)}-(?P<flavor>install_only_stripped|install_only)\.tar\.gz$'
    )
    candidates: list[tuple[int, dict]] = []
    for asset in assets:
        name = asset.get('name')
        if not isinstance(name, str):
            continue
        match = pattern.fullmatch(name)
        if not match:
            continue
        # ``stripped`` reduce el tamaño sin cambiar el runtime necesario para Bagron.
        priority = 0 if match.group('flavor') == 'install_only_stripped' else 1
        candidates.append((priority, asset))

    if not candidates:
        raise RuntimeError(
            f'No hay un runtime CPython {python_minor} para {target} '
            f'({triple}) en la release consultada.'
        )
    candidates.sort(key=lambda item: (item[0], item[1]['name']))
    return candidates[0][1]


def _download(url: str, destination: Path) -> None:
    """Descarga un archivo binario sin cargarlo entero en memoria."""
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request) as response, destination.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    except urllib.error.URLError as error:
        raise RuntimeError(f'No se pudo descargar {url}: {error}') from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_archive(archive_path: Path, destination: Path) -> None:
    """Extrae el tarball y rechaza rutas que salgan del directorio temporal."""
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with tarfile.open(archive_path, mode='r:gz') as archive:
        for member in archive.getmembers():
            member_path = (destination / member.name).resolve()
            if member_path != root and root not in member_path.parents:
                raise RuntimeError(f'El runtime contiene una ruta insegura: {member.name}')
        # Python 3.14 proporciona el filtro seguro para miembros y enlaces.
        archive.extractall(destination, filter='data')


def _find_distribution_root(extract_dir: Path, target: str) -> tuple[Path, Path]:
    """Encuentra la raíz ``python/`` y el ejecutable de la distribución extraída."""
    if target == 'windows':
        executables = sorted(extract_dir.rglob('python.exe'), key=lambda path: len(path.parts))
        if not executables:
            raise RuntimeError('El tarball no contiene python.exe.')
        executable = executables[0]
        return executable.parent, executable

    executables = sorted(
        (
            path
            for path in extract_dir.rglob('python*')
            if path.is_file() and path.parent.name == 'bin' and path.name != 'python-config'
        ),
        key=lambda path: len(path.parts),
    )
    if not executables:
        raise RuntimeError('El tarball no contiene un Python ejecutable en bin/.')
    executable = executables[0]
    return executable.parent.parent, executable


def _runtime_executable(runtime_dir: Path, target: str) -> Path:
    """Devuelve la ruta estable del Python preparado."""
    if target == 'windows':
        executable = runtime_dir / 'python.exe'
        if not executable.is_file():
            raise RuntimeError('El runtime Windows preparado no contiene python.exe.')
        return executable

    bin_dir = runtime_dir / 'bin'
    executable = bin_dir / 'python'
    if not executable.is_file():
        candidates = sorted(
            path for path in bin_dir.glob('python*') if path.is_file() and 'config' not in path.name
        )
        if not candidates:
            raise RuntimeError('El runtime Linux preparado no contiene bin/python.')
        actual = candidates[0]
        # El empaquetador registra los aliases; evita duplicar los bytes del
        # ejecutable y deja que el instalador reconstruya el enlace.
        if executable.is_symlink():
            raise RuntimeError(f'Enlace Python dañado: {executable}')
        executable.symlink_to(actual.name)
    return executable


def _ignore_runtime_files(path: str, names: list[str]) -> set[str]:
    """Omite terminfo, que no interviene en Bagron y contiene symlinks masivos."""
    if Path(path).name == 'share':
        return {'terminfo'} if 'terminfo' in names else set()
    return set()


def _verify_runtime(executable: Path) -> None:
    """Comprueba que el runtime es ejecutable y trae pip."""
    version = subprocess.run(
        [str(executable), '--version'],
        capture_output=True,
        text=True,
        check=False,
    )
    if version.returncode != 0:
        raise RuntimeError(f'El Python portable no se pudo ejecutar: {version.stderr.strip()}')

    pip = subprocess.run(
        [str(executable), '-m', 'pip', '--version'],
        capture_output=True,
        text=True,
        check=False,
    )
    if pip.returncode != 0:
        raise RuntimeError(
            'El Python portable no incluye pip; no se puede preparar vnma. '
            f'{pip.stderr.strip()}'
        )


def prepare_runtime(
    output_dir: Path,
    *,
    target: str,
    python_minor: str = DEFAULT_PYTHON_MINOR,
    release_tag: str | None = None,
) -> Path:
    """Descarga, verifica y prepara un runtime portable para PyInstaller."""
    if target not in TARGET_TRIPLES:
        raise ValueError(f'Plataforma no soportada: {target}')

    resolved_tag = _resolve_release_tag(release_tag)
    api_url = PYTHON_STANDALONE_API_URL.format(
        tag=urllib.parse.quote(resolved_tag, safe=''),
    )
    release = _request_json(api_url)
    assets = release.get('assets')
    if not isinstance(assets, list):
        raise RuntimeError('La release de Python no contiene una lista de assets.')
    asset = _select_asset(assets, python_minor=python_minor, target=target)
    download_url = asset.get('browser_download_url')
    expected_digest = asset.get('digest')
    if not isinstance(download_url, str) or not download_url:
        raise RuntimeError(f'El asset {asset.get("name")} no tiene URL de descarga.')
    if not isinstance(expected_digest, str) or not expected_digest.startswith('sha256:'):
        raise RuntimeError(f'El asset {asset.get("name")} no tiene digest SHA-256.')
    expected_sha256 = expected_digest.removeprefix('sha256:')

    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    print(f'Preparando CPython portable {python_minor} para {target}...')
    print(f'  Release: {resolved_tag}')
    print(f'  Asset:   {asset["name"]}')

    with tempfile.TemporaryDirectory(prefix='bagron-python-') as temporary:
        temporary_dir = Path(temporary)
        archive_path = temporary_dir / asset['name']
        _download(download_url, archive_path)
        actual_sha256 = _sha256(archive_path)
        if actual_sha256 != expected_sha256:
            raise RuntimeError(
                f'Hash SHA-256 incorrecto para {asset["name"]}: '
                f'esperado {expected_sha256}, obtenido {actual_sha256}.'
            )

        extract_dir = temporary_dir / 'extracted'
        _extract_archive(archive_path, extract_dir)
        distribution_root, _ = _find_distribution_root(extract_dir, target)

        if output_dir.exists():
            shutil.rmtree(output_dir)
        # Los enlaces POSIX se preservan para evitar duplicar los binarios
        # versionados de Python y las bibliotecas compartidas. Los enlaces se
        # excluyen del onefile mediante un manifiesto que restaura el instalador.
        # Windows se copia sin symlinks (las duplicaciones de bytes se tratan
        # igualmente por el manifiesto después de instalar vnma).
        shutil.copytree(
            distribution_root,
            output_dir,
            symlinks=(target == 'linux'),
            ignore=_ignore_runtime_files,
        )

    executable = _runtime_executable(output_dir, target)
    _verify_runtime(executable)
    manifest = {
        'provider': 'astral-sh/python-build-standalone',
        'release_tag': resolved_tag,
        'asset': asset['name'],
        'sha256': expected_sha256,
        'target': target,
        'python_minor': python_minor,
    }
    (output_dir / 'bagron-python-runtime.json').write_text(
        json.dumps(manifest, indent=2) + '\n',
        encoding='utf-8',
    )
    print(f'  Runtime listo en {output_dir}')
    return executable


def main() -> int:
    parser = argparse.ArgumentParser(description='Prepara el Python portable de Bagron.')
    parser.add_argument('--platform', choices=sorted(TARGET_TRIPLES), required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--python-minor', default=DEFAULT_PYTHON_MINOR)
    parser.add_argument('--release-tag', help='Tag de python-build-standalone; por defecto, latest.')
    args = parser.parse_args()

    try:
        prepare_runtime(
            args.output_dir,
            target=args.platform,
            python_minor=args.python_minor,
            release_tag=args.release_tag,
        )
    except (OSError, RuntimeError, tarfile.TarError) as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

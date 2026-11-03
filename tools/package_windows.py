"""Genera el paquete fuente instalable de Bagron para Windows x86_64."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from installer import BAGRON_VERSION


PACKAGE_DIRECTORIES = (
    'core',
    'tools',
    'examples',
    'docs',
    'badge',
    'changelog',
)
PACKAGE_FILES = (
    'installer.py',
    'main.py',
    'README.md',
    'LICENSE',
    'vnma.toml.example',
)
AOT_PACKAGE_FILES = (
    'build/aot/bagron_aot.dll',
    'build/aot/gram_parser_manifest.json',
)
EXCLUDED_PARTS = {
    '.git',
    '.ia',
    '.pytest_cache',
    '__pycache__',
    'build',
    'dist',
    'log',
    'tests',
    'vendor',
}
def _zip_info(arcname: str, mode: int) -> zipfile.ZipInfo:
    """Crea metadatos ZIP estables y conserva el bit ejecutable cuando aplica."""
    info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (mode & 0xFFFF) << 16
    return info


def _add_file(archive: zipfile.ZipFile, source: Path, arcname: str) -> None:
    mode = source.stat().st_mode
    info = _zip_info(arcname, mode)
    archive.writestr(info, source.read_bytes())


def _add_tree(archive: zipfile.ZipFile, source_root: Path, relative: str, package_root: str) -> None:
    source = source_root / relative
    if not source.is_dir():
        return
    for path in sorted(source.rglob('*')):
        if not path.is_file():
            continue
        path_parts = set(path.relative_to(source_root).parts)
        if path_parts & EXCLUDED_PARTS or path.suffix in {'.pyc', '.pyo'}:
            continue
        archive_name = f'{package_root}/{path.relative_to(source_root).as_posix()}'
        _add_file(archive, path, archive_name)


def build_package(source_root: Path, output: Path) -> Path:
    """Empaqueta fuentes, AOT y configuración sin incluir dependencias locales."""
    package_root = f'Bagron-{BAGRON_VERSION}'
    output.parent.mkdir(parents=True, exist_ok=True)
    missing_aot = [str(source_root / relative) for relative in AOT_PACKAGE_FILES
                   if not (source_root / relative).is_file()]
    if missing_aot:
        raise FileNotFoundError(
            'Faltan artefactos AOT de Windows: ' + ', '.join(missing_aot)
        )

    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in PACKAGE_DIRECTORIES:
            _add_tree(archive, source_root, relative, package_root)
        for relative in PACKAGE_FILES + AOT_PACKAGE_FILES:
            _add_file(archive, source_root / relative, f'{package_root}/{relative}')

        for relative in ('libs', 'modules'):
            archive.writestr(_zip_info(f'{package_root}/{relative}/', 0o755), b'')

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description='Genera el paquete Windows de Bagron')
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('dist') / f'Bagron-{BAGRON_VERSION}-windows-x86_64.zip',
    )
    args = parser.parse_args()
    output = build_package(PROJECT_ROOT, args.output.resolve())
    print(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

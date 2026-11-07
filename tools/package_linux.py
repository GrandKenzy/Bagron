"""Genera el paquete fuente instalable de Bagron para Linux."""

from __future__ import annotations

import argparse
import gzip
import os
from pathlib import Path
import sys
import tarfile

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
    'install.sh',
    'main.py',
    'README.md',
    'LICENSE',
)
EXCLUDED_PARTS = {
    '.git',
    '.ia',
    '.pytest_cache',
    '__pycache__',
    'build',
    'log',
    'tests',
    'vendor',
}
SOURCE_DATE_EPOCH = int(os.environ.get('SOURCE_DATE_EPOCH', '0'))


def _tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
    parts = set(Path(info.name).parts)
    if parts & EXCLUDED_PARTS:
        return None
    if info.name.endswith(('.pyc', '.pyo')):
        return None
    if info.name.endswith('/install.sh'):
        info.mode = 0o755
    info.mtime = SOURCE_DATE_EPOCH
    info.uid = 0
    info.gid = 0
    info.uname = ''
    info.gname = ''
    return info


def build_package(source_root: Path, output: Path) -> Path:
    """Empaqueta una distribución fuente reproducible y sin dependencias vendoreadas."""
    package_root = f'Bagron-{BAGRON_VERSION}'
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open('wb') as raw_file:
        with gzip.GzipFile(
            filename='',
            mode='wb',
            fileobj=raw_file,
            mtime=SOURCE_DATE_EPOCH,
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode='w') as archive:
                for relative in PACKAGE_DIRECTORIES:
                    source = source_root / relative
                    if source.is_dir():
                        archive.add(
                            source,
                            arcname=f'{package_root}/{relative}',
                            recursive=True,
                            filter=_tar_filter,
                        )

                for relative in PACKAGE_FILES:
                    source = source_root / relative
                    if source.is_file():
                        archive.add(
                            source,
                            arcname=f'{package_root}/{relative}',
                            recursive=False,
                            filter=_tar_filter,
                        )

                # Las carpetas vacías son creadas también por installer.py, pero
                # mantenerlas en el paquete hace más claro su layout para inspección.
                for relative in ('libs',):
                    info = tarfile.TarInfo(f'{package_root}/{relative}/')
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    info.mtime = SOURCE_DATE_EPOCH
                    info.uid = 0
                    info.gid = 0
                    info.uname = ''
                    info.gname = ''
                    archive.addfile(info)

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description='Genera el paquete Linux de Bagron')
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('dist') / f'Bagron-{BAGRON_VERSION}-linux-x86_64.tar.gz',
    )
    args = parser.parse_args()
    output = build_package(PROJECT_ROOT, args.output.resolve())
    print(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

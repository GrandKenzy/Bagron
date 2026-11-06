"""Assemble the offline compiler payload shipped inside release installers.

This does not freeze a version of Gram. It packages the exact vendor tree and
AOT library produced by the release job against Gram's current main branch.
The portable Python runtime is bundled separately by PyInstaller.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.version import BAGRON_VERSION


COMPILER_DIRECTORIES = (
    'core', 'tools', 'modules', 'examples', 'docs', 'badge', 'changelog',
)
COMPILER_FILES = (
    'main.py', 'installer.py', 'README.md', 'LICENSE', 'install.sh',
    'vnma.toml',
)
OPTIONAL_FILES = ('vnma.lock', 'vnma.toml.example')


def _aot_name(platform_name: str) -> str:
    if platform_name == 'windows':
        return 'bagron_aot.dll'
    if platform_name == 'linux':
        return 'libbagron_aot.so'
    raise ValueError(f'Unsupported release platform: {platform_name}')


def _runtime_path(root: Path, platform_name: str) -> Path:
    runtime = root / 'build' / 'portable-python'
    return runtime / ('python.exe' if platform_name == 'windows' else 'bin/python')


def _skip_generated(directory: str, names: list[str]) -> set[str]:
    return {
        name for name in names
        if name in {'.git', '__pycache__', '.pytest_cache', '.venv'}
        or name.endswith(('.pyc', '.pyo'))
    }


def prepare_payload(root: Path, destination: Path, *, platform_name: str) -> Path:
    root = root.resolve()
    destination = destination.resolve()
    if destination == root or root in destination.parents and destination.name != 'release-payload':
        raise ValueError('The output must be a dedicated release-payload directory.')

    library = root / 'build' / 'aot' / _aot_name(platform_name)
    manifest = library.parent / 'gram_parser_manifest.json'
    mandatory = [
        root / 'core', root / 'tools', root / 'main.py',
        root / 'vendor' / 'gram', root / 'vendor' / 'llvmlite',
        root / 'vnma.toml', _runtime_path(root, platform_name),
        library, manifest,
    ]
    missing = [str(path) for path in mandatory if not path.exists()]
    if missing:
        raise FileNotFoundError('Release prerequisites missing: ' + ', '.join(missing))

    grammar = json.loads(manifest.read_text(encoding='utf-8'))
    grammar_id = grammar.get('grammar_id')
    try:
        int(grammar_id, 0) if isinstance(grammar_id, str) else int(grammar_id)
    except (ValueError, TypeError) as error:
        raise ValueError('Invalid Gram AOT grammar_id in manifest') from error

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for name in COMPILER_DIRECTORIES:
        source = root / name
        if source.is_dir():
            shutil.copytree(source, destination / name, ignore=_skip_generated)
    for name in COMPILER_FILES:
        source = root / name
        if source.is_file():
            shutil.copy2(source, destination / name)
    for name in OPTIONAL_FILES:
        source = root / name
        if source.is_file():
            shutil.copy2(source, destination / name)

    shutil.copytree(root / 'vendor', destination / 'vendor', ignore=_skip_generated)
    aot_destination = destination / 'build' / 'aot'
    aot_destination.mkdir(parents=True)
    shutil.copy2(library, aot_destination / library.name)
    shutil.copy2(manifest, aot_destination / manifest.name)
    metadata = {
        'format_version': 1,
        'bagron_version': BAGRON_VERSION,
        'platform': platform_name,
        'gram_branch': 'main',
        'aot_library': library.name,
        'aot_sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
        'grammar_id': grammar_id,
    }
    (destination / 'bagron-prebuilt.json').write_text(
        json.dumps(metadata, indent=2) + '\n', encoding='utf-8'
    )
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output-dir', type=Path, default=Path('build/release-payload'))
    parser.add_argument(
        '--platform', choices=('linux', 'windows'),
        default='windows' if os.name == 'nt' else 'linux',
    )
    args = parser.parse_args()
    try:
        output = prepare_payload(args.source, args.output_dir, platform_name=args.platform)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

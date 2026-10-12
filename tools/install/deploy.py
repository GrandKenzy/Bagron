"""Copia de los componentes de EGL (core, libraries, source, tools...) al destino."""
from __future__ import annotations

import shutil
from pathlib import Path

from tools import config


def _same_dir(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except Exception:
        return False


def copy_components(source_root: Path, target_dir: Path) -> None:
    if _same_dir(source_root, target_dir):
        return

    for folder_name in config.COMPONENT_FOLDERS:
        src, dst = source_root / folder_name, target_dir / folder_name
        if src.is_dir():
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)

    for folder_name in config.COMPONENT_MERGE_FOLDERS:
        src, dst = source_root / folder_name, target_dir / folder_name
        if src.is_dir():
            shutil.copytree(
                src, dst, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(*config.EGLLIBS_IGNORE_PATTERNS),
            )

    for file_name in config.COMPONENT_FILES:
        src = source_root / file_name
        if src.is_file():
            shutil.copy2(src, target_dir / file_name)

    tools_src, tools_dst = source_root / config.TOOLS_DIRNAME, target_dir / config.TOOLS_DIRNAME
    if tools_src.is_dir():
        shutil.rmtree(tools_dst, ignore_errors=True)
        shutil.copytree(tools_src, tools_dst, ignore=shutil.ignore_patterns(*config.TOOLS_IGNORE_PATTERNS))

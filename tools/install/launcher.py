"""Configuración de lanzadores de EGL (`egl.exe` precompilado y shim `egl.cmd`)."""
from __future__ import annotations

import shutil
from pathlib import Path

from tools import config
from tools.install.paths import InstallLayout


def write_cmd_shim(target_cmd: Path) -> None:
    target_cmd.write_text(config.CMD_SHIM, encoding="utf-8")


def build_launcher(source_root: Path, layout: InstallLayout) -> bool:
    """Copia el binario precompilado `egl.exe` si existe y genera `egl.cmd`."""
    tools_dir = source_root / config.TOOLS_DIRNAME
    prebuilt = tools_dir / config.LAUNCHER_PREBUILT
    built = False

    if prebuilt.is_file():
        shutil.copy2(prebuilt, layout.exe)
        built = True

    write_cmd_shim(layout.cmd)
    return built

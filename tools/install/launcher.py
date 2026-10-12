"""Configuración de lanzadores de EGL (`egl.exe`, `egl.cmd`, `egl-uninstall.cmd`)."""
from __future__ import annotations

import shutil
from pathlib import Path

from tools import config
from tools.install.paths import InstallLayout

UNINSTALL_CMD_SHIM = (
    "@echo off\r\n"
    "setlocal\r\n"
    "set \"ROOT=%~dp0..\"\r\n"
    "if exist \"%ROOT%\\python\\python.exe\" (\r\n"
    "    \"%ROOT%\\python\\python.exe\" \"%~dp0uninstaller.py\" --target \"%ROOT%\" %*\r\n"
    ") else (\r\n"
    "    python \"%~dp0uninstaller.py\" --target \"%ROOT%\" %*\r\n"
    ")\r\n"
)


def write_cmd_shim(target_cmd: Path) -> None:
    target_cmd.write_text(config.CMD_SHIM, encoding="utf-8")


def write_uninstaller_shim(target_cmd: Path) -> None:
    target_cmd.write_text(UNINSTALL_CMD_SHIM, encoding="utf-8")


def build_launcher(source_root: Path, layout: InstallLayout) -> bool:
    """Configura el lanzador `egl.exe` / `egl.cmd` y el desinstalador `egl-uninstall.cmd` en `bin/`."""
    tools_dir = source_root / config.TOOLS_DIRNAME
    prebuilt = tools_dir / config.LAUNCHER_PREBUILT
    built = False

    if prebuilt.is_file():
        shutil.copy2(prebuilt, layout.exe)
        built = True

    write_cmd_shim(layout.cmd)

    # Desplegar uninstaller en bin/
    uninstaller_src = tools_dir / "uninstaller.py"
    if uninstaller_src.is_file():
        shutil.copy2(uninstaller_src, layout.uninstaller_py)

    write_uninstaller_shim(layout.uninstaller_cmd)
    return built

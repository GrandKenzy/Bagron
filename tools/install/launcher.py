"""Generación del lanzador nativo `egl.exe` y del shim `egl.cmd`."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from tools import config
from tools.install.paths import InstallLayout


def _run_compiler(cmd: list[str], output_exe: Path) -> bool:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, creationflags=config.subprocess_flags())
        return res.returncode == 0 and output_exe.is_file()
    except Exception:
        return False


def compile_launcher_binary(source_c: Path, output_exe: Path) -> bool:
    gcc_bin = shutil.which("gcc")
    if gcc_bin and _run_compiler([gcc_bin, *config.GCC_FLAGS, str(source_c), "-o", str(output_exe)], output_exe):
        return True
    cl_bin = shutil.which("cl")
    if cl_bin and _run_compiler([cl_bin, *config.MSVC_FLAGS, str(source_c), f"/Fe:{output_exe}"], output_exe):
        return True
    return False


def write_cmd_shim(target_cmd: Path) -> None:
    target_cmd.write_text(config.CMD_SHIM, encoding="utf-8")


def build_launcher(source_root: Path, layout: InstallLayout) -> bool:
    """Compila o copia `egl.exe` en bin/ y escribe `egl.cmd`. Devuelve True si hay .exe."""
    tools_dir = source_root / config.TOOLS_DIRNAME
    launcher_c = tools_dir / config.LAUNCHER_SOURCE
    built = launcher_c.is_file() and compile_launcher_binary(launcher_c, layout.exe)

    if not built:
        prebuilt = tools_dir / config.LAUNCHER_PREBUILT
        if prebuilt.is_file():
            shutil.copy2(prebuilt, layout.exe)
            built = True

    write_cmd_shim(layout.cmd)
    return built

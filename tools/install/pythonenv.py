"""Detección e instalación de Python 3.13+ (sistema o embebido portable)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from tools import config
from tools.install.console import log

_CHECK_CODE = f"import sys; sys.exit(0 if sys.version_info >= {config.MIN_PYTHON} else 1)"


def _frozen_exe() -> str:
    return str(Path(sys.executable).resolve()).lower() if getattr(sys, "frozen", False) else ""


def _meets_minimum(executable: str) -> bool:
    """True si `executable` es un Python >= MIN_PYTHON (y no es el propio instalador)."""
    installer_exe = _frozen_exe()
    if installer_exe and str(Path(executable).resolve()).lower() == installer_exe:
        return False
    try:
        res = subprocess.run(
            [executable, "-c", _CHECK_CODE],
            capture_output=True,
            creationflags=config.subprocess_flags(),
            timeout=config.PYTHON_CHECK_TIMEOUT,
        )
        return res.returncode == 0
    except Exception:
        return False


def _find_in_user_programs() -> str | None:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return None
    py_user = Path(local_app_data) / "Programs" / "Python"
    if not py_user.is_dir():
        return None
    try:
        for entry in sorted(py_user.iterdir(), reverse=True):
            if entry.name.startswith(config.PYTHON_USER_PREFIXES):
                exe = entry / "python.exe"
                if exe.is_file():
                    return str(exe)
    except Exception:
        pass
    return None


def _find_in_program_files() -> str | None:
    prog_files = os.environ.get("ProgramFiles", "")
    if not prog_files:
        return None
    for name in config.PYTHON_SYSTEM_DIRS:
        exe = Path(prog_files) / name / "python.exe"
        if exe.is_file():
            return str(exe)
    return None


def find_system_python() -> str | None:
    """Busca un ejecutable de Python 3.13+ de forma rápida y segura."""
    if not getattr(sys, "frozen", False) and sys.version_info >= config.MIN_PYTHON:
        return sys.executable

    found = _find_in_user_programs() or _find_in_program_files()
    if found:
        return found

    for cand in config.PYTHON_PATH_COMMANDS:
        path = shutil.which(cand)
        if path and _meets_minimum(path):
            return path
    return None


def is_python_313_or_higher(py_executable: str | None = None) -> bool:
    if py_executable:
        return _meets_minimum(py_executable)
    return find_system_python() is not None


def _configure_pth(dest_dir: Path) -> None:
    pth_files = list(dest_dir.glob("*._pth"))
    if pth_files:
        pth = pth_files[0]
        pth.write_text(pth.read_text(encoding="utf-8") + config.PYTHON_PTH_EXTRA_LINES, encoding="utf-8")


def download_embedded_python(dest_dir: Path, progress_cb=None) -> bool:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if (dest_dir / "python.exe").is_file():
        if progress_cb:
            progress_cb(100, "Python embebido ya presente.")
        log(f"Python embebido ya presente en: '{dest_dir}'")
        return True

    log("Descargando entorno portable de Python 3.13 desde python.org...")
    zip_dest = dest_dir.parent / config.PYTHON_EMBED_TEMP_ZIP
    try:
        req = urllib.request.Request(config.PYTHON_EMBED_URL, headers={"User-Agent": config.USER_AGENT})
        with urllib.request.urlopen(req, timeout=config.PYTHON_DOWNLOAD_TIMEOUT) as resp, open(zip_dest, "wb") as f:
            total = resp.headers.get("content-length")
            total = int(total) if total else None
            downloaded = 0
            while True:
                chunk = resp.read(config.PYTHON_DOWNLOAD_CHUNK)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total:
                    pct = int(downloaded / total * 100)
                    progress_cb(pct, f"Descargando Python 3.13: {pct}% ({downloaded // (1024 * 1024)} MB)")

        if progress_cb:
            progress_cb(100, "Extrayendo entorno de Python...")
        log("Extrayendo entorno de Python...")
        with zipfile.ZipFile(zip_dest, "r") as zf:
            zf.extractall(dest_dir)
        zip_dest.unlink(missing_ok=True)

        _configure_pth(dest_dir)
        log(f"¡Python 3.13 portable configurado exitosamente en: '{dest_dir}'!")
        return True
    except Exception as e:
        log(f"Error al descargar/configurar Python embebido: {e}", tag="Installer Error")
        return False

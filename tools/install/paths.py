"""Resolución de rutas de EGL (código fuente, instalación, vendor y caché)."""
from __future__ import annotations

import sys
from pathlib import Path

from tools import config


def get_project_root() -> Path:
    """Raíz del proyecto (carpeta que contiene `tools/`)."""
    return Path(__file__).resolve().parent.parent.parent


def get_default_install_dir() -> Path:
    return config.default_install_dir()


def get_cache_dir() -> Path:
    return get_default_install_dir().parent / config.SOURCE_CACHE_DIRNAME


def get_private_vendor_dir() -> Path:
    """Vendor privado del árbol de desarrollo (`<raíz>/.egl/vendor`)."""
    return get_project_root().joinpath(*config.DEV_VENDOR_PARTS)


def get_source_root() -> Path:
    """Raíz de los archivos de EGL, soportando PyInstaller y modo desarrollo."""
    # 1. Congelado en PyInstaller (_MEIPASS)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        mei = Path(sys._MEIPASS)
        if (mei / "core").is_dir():
            return mei

    # 2. Árbol de código fuente / repositorio de desarrollo
    dev_root = get_project_root()
    if (dev_root / "core").is_dir():
        return dev_root

    # 3. Directorio adyacente al ejecutable
    exe_dir = Path(sys.executable).resolve().parent
    if (exe_dir / "core").is_dir():
        return exe_dir

    return dev_root


def find_local_gram(source_root: Path) -> Path | None:
    """Busca una copia local de Gram dentro del código fuente."""
    for parts in (config.DEV_VENDOR_PARTS, (config.VENDOR_DIRNAME,)):
        cand = source_root.joinpath(*parts, config.GRAM_DIRNAME)
        if cand.is_dir():
            return cand
    return None


class InstallLayout:
    """Rutas derivadas de un directorio de instalación."""

    def __init__(self, target_dir: Path):
        self.root = Path(target_dir).resolve()
        self.bin = self.root / config.BIN_DIRNAME
        self.python = self.root / config.PYTHON_DIRNAME
        self.vendor = self.root / config.VENDOR_DIRNAME
        self.gram = self.vendor / config.GRAM_DIRNAME
        self.exe = self.bin / config.EXE_NAME
        self.cmd = self.bin / config.CMD_NAME

    def create(self) -> None:
        for name in config.LAYOUT_DIRS:
            (self.root / name).mkdir(parents=True, exist_ok=True)

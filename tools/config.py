"""
Configuración central de la instalación de EGL.

Todas las rutas, nombres, URLs y opciones del instalador se definen aquí.
Los módulos de `tools/install/` no deben tener valores "hardcodeados":
cualquier cambio de nombre, ruta o comportamiento se hace únicamente en este archivo.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Identidad
# ---------------------------------------------------------------------------
APP_NAME = "EGL"
EXE_NAME = "egl.exe"
CMD_NAME = "egl.cmd"
ENTRY_SCRIPT = "egl.py"
USER_AGENT = "EGL-Installer"

# ---------------------------------------------------------------------------
# Python requerido y entorno portable
# ---------------------------------------------------------------------------
MIN_PYTHON = (3, 13)
PYTHON_EMBED_URL = "https://www.python.org/ftp/python/3.13.2/python-3.13.2-embed-amd64.zip"
PYTHON_EMBED_TEMP_ZIP = "_py_embed_temp.zip"
# Candidatos de instalación de Python (Windows), de más nuevo a más antiguo.
PYTHON_USER_PREFIXES = ("Python313", "Python314", "Python315", "Python316")
PYTHON_SYSTEM_DIRS = ("Python316", "Python315", "Python314", "Python313")
PYTHON_PATH_COMMANDS = ("py", "python")
PYTHON_CHECK_TIMEOUT = 2
# Líneas añadidas al archivo ._pth del Python embebido (rutas relativas al install).
PYTHON_PTH_EXTRA_LINES = "\n.\n..\n../vendor\n../vendor/Gram\nimport site\n"

# ---------------------------------------------------------------------------
# Repositorio y descargas
# ---------------------------------------------------------------------------
GITHUB_REPO = "GrandKenzy/EGL"
SOURCE_ARCHIVE_URLS = (
    f"https://github.com/{GITHUB_REPO}/archive/refs/tags/v0.2.0.zip",
    f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.zip",
)
SOURCE_CACHE_DIRNAME = "_egl_src_cache"
SOURCE_DOWNLOAD_TIMEOUT = 15
PYTHON_DOWNLOAD_TIMEOUT = 30
PYTHON_DOWNLOAD_CHUNK = 65536

# Librería privada 'gram'
GRAM_REPO_URL = "https://github.com/GrandKenzy/Gram.git"
GRAM_ZIP_URL = "https://github.com/GrandKenzy/Gram/archive/refs/heads/main.zip"
GRAM_PACKAGE = "gram"
GRAM_DIRNAME = "Gram"
GRAM_ZIP_TEMP = "_gram_temp.zip"
GRAM_EXTRACT_TEMP = "_temp_gram_extract"
GRAM_DOWNLOAD_CHUNK = 16384

# ---------------------------------------------------------------------------
# Estructura del directorio de instalación
# ---------------------------------------------------------------------------
INSTALL_PARENT_DIRS = ("Programs",)          # bajo %LOCALAPPDATA%
BIN_DIRNAME = "bin"
PYTHON_DIRNAME = "python"
VENDOR_DIRNAME = "vendor"
# Ruta de vendor dentro del árbol de desarrollo (relativa a la raíz del proyecto).
DEV_VENDOR_PARTS = (".egl", "vendor")

# Carpetas completas que se copian desde el código fuente.
COMPONENT_FOLDERS = ("core",)
# Carpetas que se fusionan (sin borrar lo existente), p. ej. librerías instaladas por el usuario.
EGLLIBS_DIRNAME = "EGLLibs"  # debe coincidir con core.packages.layout.EGLLIBS_DIRNAME
COMPONENT_MERGE_FOLDERS = (EGLLIBS_DIRNAME,)
EGLLIBS_IGNORE_PATTERNS = (".cache", ".temp", "__pycache__")
# Estructura vacía de EGLLibs que se crea siempre en el destino.
EGLLIBS_LAYOUT = (
    "libraries",
    "backends/c/externs",
    "backends/c/includes",
    "backends/c/libraries",
    "backends/c/bin",
    "backends/c/lib",
    ".cache",
    ".temp",
)
# Archivos sueltos que se copian si existen.
COMPONENT_FILES = ("egl.py", "README.md", "LICENSE")
# Carpeta `tools` (lógica de instalación) que viaja con la instalación.
TOOLS_DIRNAME = "tools"
TOOLS_IGNORE_PATTERNS = ("__pycache__", "*.pyc", "installer_gui.py")
# Carpetas que se crean siempre en el destino.
LAYOUT_DIRS = (BIN_DIRNAME, *COMPONENT_FOLDERS, VENDOR_DIRNAME, *(f"{EGLLIBS_DIRNAME}/{d}" for d in EGLLIBS_LAYOUT))

# ---------------------------------------------------------------------------
# Lanzador nativo
# ---------------------------------------------------------------------------
LAUNCHER_SOURCE = "launcher.c"
LAUNCHER_PREBUILT = "egl.exe"
CMD_SHIM = (
    "@echo off\r\n"
    "setlocal\r\n"
    "set \"ROOT=%~dp0..\"\r\n"
    "if exist \"%ROOT%\\python\\python.exe\" (\r\n"
    "    \"%ROOT%\\python\\python.exe\" \"%ROOT%\\egl.py\" %*\r\n"
    ") else (\r\n"
    "    python \"%ROOT%\\egl.py\" %*\r\n"
    ")\r\n"
)
# Compiladores C conocidos (detección rápida para el instalador gráfico).

# ---------------------------------------------------------------------------
# PATH de Windows
# ---------------------------------------------------------------------------
REGISTRY_ENV_KEY = r"Environment"
REGISTRY_PATH_VALUE = "Path"
WM_SETTINGCHANGE_TIMEOUT_MS = 5000
CREATE_NO_WINDOW = 0x08000000


def subprocess_flags() -> int:
    """Flags de creación de subprocesos (sin ventana en Windows)."""
    import sys
    return CREATE_NO_WINDOW if sys.platform == "win32" else 0


def default_install_dir() -> Path:
    """Directorio de instalación por defecto (%LOCALAPPDATA%\\Programs\\EGL)."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base.joinpath(*INSTALL_PARENT_DIRS, APP_NAME)


@dataclass
class InstallOptions:
    """Opciones de una ejecución de instalación."""
    target_dir: Path | None = None
    force_embed_python: bool = False
    add_to_path: bool = True
    source_root: Path | None = None
    extra: dict = field(default_factory=dict)

"""API pública del sistema de instalación de EGL."""
from tools.install.console import install_safe_streams
from tools.install.deploy import copy_components
from tools.install.launcher import build_launcher
from tools.install.paths import (
    InstallLayout,
    get_default_install_dir,
    get_project_root,
    get_source_root,
)
from tools.install.pipeline import install_egl, run_install, uninstall_egl
from tools.install.pythonenv import download_embedded_python, find_system_python, is_python_313_or_higher
from tools.install.sources import ensure_source_files
from tools.install.status import get_system_status
from tools.install.winpath import add_to_user_path, remove_from_user_path

__all__ = [
    "InstallLayout",
    "add_to_user_path",
    "build_launcher",
    "copy_components",
    "download_embedded_python",
    "ensure_source_files",
    "find_system_python",
    "get_default_install_dir",
    "get_project_root",
    "get_source_root",
    "get_system_status",
    "install_egl",
    "install_safe_streams",
    "is_python_313_or_higher",
    "remove_from_user_path",
    "run_install",
    "uninstall_egl",
]

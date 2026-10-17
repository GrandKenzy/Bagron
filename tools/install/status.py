"""Diagnóstico rápido del sistema para el instalador gráfico."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from tools import config
from tools.install.paths import get_default_install_dir
from tools.install.pythonenv import find_system_python


def _python_status() -> tuple[bool, str]:
    sys_py = find_system_python()
    if sys_py:
        return True, f"Python detectado en: {sys_py}"
    return False, "No detectado (se instalará versión portable)"


def _gram_status() -> tuple[bool, str]:
    try:
        if importlib.util.find_spec("gram") is not None:
            return True, "Framework Gram disponible"
    except Exception:
        pass
    return False, "No detectado en el entorno Python (gestionar con vnma o pip)"


def get_system_status() -> dict:
    py_ok, py_msg = _python_status()
    gram_ok, gram_msg = _gram_status()
    return {
        "default_dir": str(get_default_install_dir()),
        "python_ok": py_ok,
        "python_msg": py_msg,
        "gram_ok": gram_ok,
        "gram_msg": gram_msg,
    }

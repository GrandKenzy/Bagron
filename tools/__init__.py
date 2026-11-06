"""
Herramientas de Bagron:
- tools.diagnostic: Diagnóstico para procesamiento y archivos logs.
- tools.console: Diagnóstico y log de consola.
- tools.config: Configuración global.
- tools.install: Módulos de instalación.
"""
from __future__ import annotations

from importlib import import_module


def __getattr__(name: str):
    """Load optional tool modules only when callers actually request them."""
    if name == "diagnostics":
        return import_module("tools.diagnostic")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "diagnostics",
]

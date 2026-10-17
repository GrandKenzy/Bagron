"""
Herramientas de Easy-C:
- tools.diagnostic: Diagnóstico para procesamiento y archivos logs.
- tools.console: Diagnóstico y log de consola.
- tools.config: Configuración global.
- tools.install: Módulos de instalación.
"""
from __future__ import annotations

from tools import console
from tools import diagnostic
from tools import diagnostic as diagnostics

__all__ = [
    "console",
    "diagnostic",
    "diagnostics",
]

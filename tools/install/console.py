"""
tools.install.console: Adaptador de compatibilidad hacia tools.console.
"""
from __future__ import annotations

from tools.console import (
    Console,
    ConsoleDiagnostics,
    ProgressCallback,
    SafeWriter,
    default_console,
    install_safe_streams,
    log,
    report,
)

__all__ = [
    "ConsoleDiagnostics",
    "Console",
    "default_console",
    "log",
    "report",
    "SafeWriter",
    "install_safe_streams",
    "ProgressCallback",
]

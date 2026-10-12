"""Utilidades de consola: salida segura y registro de mensajes del instalador."""
from __future__ import annotations

import sys
from typing import Callable

ProgressCallback = Callable[[int, str, str], None]


class SafeWriter:
    """Evita OSError [Errno 22] al escribir en stdout/stderr de ejecutables GUI de Windows."""

    def __init__(self, original):
        self.original = original

    def write(self, s):
        try:
            if self.original:
                return self.original.write(s)
        except Exception:
            pass

    def flush(self):
        try:
            if self.original:
                return self.original.flush()
        except Exception:
            pass


def install_safe_streams() -> None:
    """Envuelve stdout/stderr en `SafeWriter` (idempotente)."""
    try:
        for name in ("stdout", "stderr"):
            stream = getattr(sys, name)
            if isinstance(stream, SafeWriter):
                continue
            if stream is None or not hasattr(stream, "write"):
                setattr(sys, name, SafeWriter(None))
            else:
                setattr(sys, name, SafeWriter(stream))
    except Exception:
        pass


def log(message: str, tag: str = "Installer") -> None:
    print(f"[{tag}] {message}", flush=True)


def report(progress: ProgressCallback | None, pct: int, stage: str, detail: str = "") -> None:
    """Notifica avance a la UI (si hay) y lo deja también en consola."""
    if detail:
        log(detail)
    if progress:
        progress(pct, stage, detail)

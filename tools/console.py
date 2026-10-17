"""
tools.console: Diagnóstico y registro de mensajes por consola.
Hereda de la clase base Diagnostics del framework Gram.
"""
from __future__ import annotations

import sys
from collections.abc import Callable

from gram import utilities

# import vendor  # noqa: F401

ProgressCallback = Callable[[int, str, str], None]


class SafeWriter:
    """Evita OSError [Errno 22] al escribir en stdout/stderr de ejecutables GUI de Windows."""

    def __init__(self, original):
        self.original = original

    def write(self, s: str):
        try:
            if self.original:
                return self.original.write(s)
        except Exception:  # noqa: BLE001, S110
            pass

    def flush(self):
        try:
            if self.original:
                return self.original.flush()
        except Exception:  # noqa: BLE001, S110
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
    except Exception:  # noqa: BLE001, S110
        pass


class ConsoleDiagnostics(utilities.Diagnostics):
    """
    Sistema de diagnóstico para la consola de Easy-C.
    Integra telemetría estructurada con salida directa y segura por terminal.
    """

    def __init__(
        self,
        file: str = "console",
        name: str = "Console",
        description: str = "Console output and telemetry",
        expose_nodes: bool = False,
        generate_log_file: bool = False,
        generate_on_error: bool = False,
        echo: bool = True,
    ) -> None:
        super().__init__(
            file=file,
            name=name,
            description=description,
            expose_nodes=expose_nodes,
            generate_log_file=generate_log_file,
            generate_on_error=generate_on_error,
        )
        self.echo = echo

    def log(self, message: str, tag: str = "Easy-C", log_type: utilities.Format.LogType = "normal") -> None:
        """Emite un mensaje etiquetado registrándolo en telemetría y en consola."""
        formatted = f"[{tag}] {message}"
        self.sender(formatted, log_type)
        if self.echo:
            try:
                print(formatted, flush=True)
            except Exception:  # noqa: BLE001, S110
                # Si fallara por codificación o descriptor inválido
                pass

    def info(self, note: str, tag: str = "INFO") -> None:
        self.log(note, tag=tag, log_type="normal")

    def success(self, note: str, tag: str = "SUCCESS") -> None:
        super().success(note)
        if self.echo:
            print(f"[{tag}] {note}", flush=True)

    def warn(self, note: str, tag: str = "WARN") -> None:
        super().warn(note)
        if self.echo:
            print(f"[{tag}] {note}", flush=True)

    def error(self, note: str, tag: str = "ERROR") -> None:
        super().error(note)
        if self.echo:
            print(f"[{tag}] {note}", file=sys.stderr, flush=True)

    def report(
        self,
        progress: ProgressCallback | None,
        pct: int,
        stage: str,
        detail: str = "",
        tag: str = "Installer",
    ) -> None:
        """Notifica avance a la UI (si hay) y lo emite también en consola."""
        if detail:
            self.log(detail, tag=tag)
        if progress:
            progress(pct, stage, detail)


# Instancia por defecto para operaciones globales
default_console = ConsoleDiagnostics()


def log(message: str, tag: str = "Installer") -> None:
    """Función de compatibilidad para registro directo en consola."""
    default_console.log(message, tag=tag)


def report(progress: ProgressCallback | None, pct: int, stage: str, detail: str = "") -> None:
    """Función de compatibilidad para reporte de avance."""
    default_console.report(progress=progress, pct=pct, stage=stage, detail=detail)


Console = ConsoleDiagnostics

__all__ = [
    "Console",
    "ConsoleDiagnostics",
    "ProgressCallback",
    "SafeWriter",
    "default_console",
    "install_safe_streams",
    "log",
    "report",
]

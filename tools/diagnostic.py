"""
tools.diagnostic: Diagnóstico y telemetría de procesamiento y archivos logs.
Hereda de la clase base Diagnostics del framework Gram.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from gram import utilities
from gram.utilities.info import Node


class Diagnostics(utilities.Diagnostics):
    """
    Sistema de diagnóstico para el procesamiento y compilación de Easy-C.
    Gestiona el registro estructurado de eventos en árbol jerárquico y
    la persistencia en archivos de log dentro del directorio log/.
    """

    def __init__(
        self,
        file: str = "processing",
        name: str = "Processor",
        description: str = "AST and code processing telemetry",
        expose_nodes: bool = True,
        generate_log_file: bool = True,
        generate_on_error: bool = False,
    ) -> None:
        super().__init__(
            file=file,
            name=name,
            description=description,
            expose_nodes=expose_nodes,
            generate_log_file=generate_log_file,
            generate_on_error=generate_on_error,
        )

    # ----------------------------------------------------------------------
    # Gestión de etapas (Stages) durante el procesamiento
    # ----------------------------------------------------------------------

    def start_stage(self, stage_name: str, description: str = "") -> Node:
        """Inicia una etapa de procesamiento creando y apilando un nodo de telemetría."""
        return self.node(stage_name, description=description, set_target=True)

    def end_stage(self) -> Node | None:
        """Finaliza la etapa actual desapilando el nodo activo del stack."""
        return self.down(get=True)

    @contextmanager
    def stage(self, stage_name: str, description: str = "") -> Iterator[Node]:
        """Context manager para delimitar etapas de procesamiento."""
        node = self.start_stage(stage_name, description=description)
        try:
            yield node
        finally:
            self.end_stage()

    # ----------------------------------------------------------------------
    # Registro de notas y eventos de telemetría
    # ----------------------------------------------------------------------

    def last_note(self):
        current = self.current()
        if isinstance(current, utilities.info.StackInfo):
            current.main.notes[-1]
        else:
            current.notes[-1]

    def info(self, note: str) -> None:
        """Registra una nota informativa en el nodo activo."""
        self.sender(note, "normal")

    def fatal(self, note: str) -> None:
        """Registra un fallo crítico en el nodo activo."""
        self.sender(note, "fatal")

    def error(self, note: str):
        """Registra un fallo en el nodo activo."""
        self.sender(note, "error")
        
    def advice(self, note: str):
        """Registra un consejo o sugerencia en el nodo activo."""
        self.sender(note, "advice")
        
    def success(self, note: str):
        """Registra éxito en el nodo activo."""
        self.sender(note, "success")
        
    def debug(self, note: str):
        """Registra un mensaje de debug en el nodo activo."""
        self.sender(note, "normal")
    # ----------------------------------------------------------------------
    # Control de estado y persistencia de logs
    # ----------------------------------------------------------------------

    @property
    def has_errors(self) -> bool:
        """Indica si se han acumulado errores en este diagnóstico."""
        return bool(self._errors)

    @property
    def errors(self) -> list[utilities.error.Error]:
        """Lista de errores acumulados."""
        return list(self._errors)

    def write_log(self) -> None:
        """Escribe manualmente el contenido de la telemetría en el archivo log asignado."""
        self.stack.write()


__all__ = [
    "Diagnostics",
]

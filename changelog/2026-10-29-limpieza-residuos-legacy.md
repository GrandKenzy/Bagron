# Limpieza de residuos legacy

Fecha: 2026-10-29

Se eliminó el alias interno `TypeInfo = TypeSpec` porque no tenía
consumidores en el proyecto. También se retiraron del `.gitignore` las reglas
para `.egl`, `*.lib.egl` y `EGLLibs`, ya que no corresponden a componentes
presentes del proyecto.

Se conservaron las llamadas LLVM a `malloc`, `free`, `memset` y `memcpy`.
Estas funciones gestionan la memoria de los `buffer` en el backend y no son
compatibilidad con sintaxis C del lenguaje.

# Modularización de la resolución de tipos

Fecha: 2026-10-29

`core/frontend/tools/types.py` pasó a ser el paquete
`core/frontend/tools/types/`, con una fachada en `__init__.py` que conserva
los imports existentes.

Las responsabilidades se separaron en `common.py`, `resolution.py`,
`postfix.py`, `calls.py`, `values.py` y `compatibility.py`. El cambio solo
reorganiza el código: mantiene la sintaxis, semántica, backend y comportamiento
del lenguaje.

# Separación de pruebas rápidas y agresivas

Fecha: 2026-10-29

Las pruebas costosas de backend, ejecución de binarios, ensamblador, bare metal,
punteros, ABI y casos únicos se movieron a `tests_aggressive/`.

`vnma test` queda reservado para la validación rápida de lógica en `tests/`.
La suite completa se ejecuta explícitamente con `vnma test tests_aggressive`.

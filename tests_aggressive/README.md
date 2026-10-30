# Pruebas agresivas

Esta carpeta contiene pruebas costosas o de integración profunda: backend LLVM,
ejecución de binarios, ensamblador, bare metal, punteros, ABI y casos únicos.

`vnma test` ejecuta la suite rápida de `tests/`. Ejecuta esta suite solo cuando
el cambio pueda afectar sus áreas:

```text
vnma test tests_aggressive
```

Las pruebas de lógica y validación superficial deben permanecer en `tests/`.

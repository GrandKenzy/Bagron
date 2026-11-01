# Pruebas agresivas

Esta carpeta contiene pruebas costosas o de integración profunda: backend LLVM,
ejecución de binarios, ensamblador, bare metal, punteros, ABI y casos únicos.

`vnma test` ejecuta la suite rápida de `tests/`. Ejecuta esta suite solo cuando
el cambio pueda afectar sus áreas:

```text
vnma test tests_aggressive
```

Las pruebas de lógica y validación superficial deben permanecer en `tests/`.

## Validación del frontend FFI de Gram

El frontend requiere la biblioteca C generada con Clang. Solo produce GIR/AST;
las pasadas semánticas y el backend LLVM siguen siendo los de Bagron:

```text
python tools/build_aot_parser.py
vnma test tests_aggressive/test_aot.py
```

La compilación y las pruebas fallan si la biblioteca FFI no está disponible.
El artefacto esperado es `build/aot/bagron_aot.dll` en Windows o su equivalente
compartido en Linux/macOS. No existe una ruta CLI ni un parser Python alternativo.

```text
vnma run main.py examples/canon/_main.bg
```

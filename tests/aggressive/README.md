# Pruebas agresivas

Esta carpeta contiene pruebas costosas o de integración profunda: backend LLVM,
ejecución de binarios, ensamblador, bare metal, punteros, ABI y casos únicos.

La suite ligera está en `tests/light/`. Esta suite se ejecuta por ruta:

```text
vnma test tests/aggressive
```

Para ejecutar una prueba individual:

```text
vnma test tests/aggressive/test_aot.py
```

## Validación del frontend FFI de Gram

El frontend requiere la biblioteca C generada con Clang. Solo produce GIR/AST;
las pasadas semánticas y el backend LLVM siguen siendo los de Bagron:

```text
python tools/build_aot_parser.py
vnma test tests/aggressive/test_aot.py
```

La compilación y las pruebas fallan si la biblioteca FFI no está disponible.
El artefacto esperado es `build/aot/bagron_aot.dll` en Windows o su equivalente
compartido en Linux/macOS. No existe una ruta CLI ni un parser Python alternativo.

El corpus de integración utilizado por `test_aot.py` está en
`tests/fixtures/canon/`.


# Pruebas agresivas

Esta carpeta contiene pruebas costosas o de integración profunda: backend LLVM,
ejecución de binarios, ensamblador, bare metal, punteros, ABI y casos únicos.

`vnma test` ejecuta la suite rápida de `tests/`. Ejecuta esta suite solo cuando
el cambio pueda afectar sus áreas:

```text
vnma test tests_aggressive
```

Las pruebas de lógica y validación superficial deben permanecer en `tests/`.

## Validación del frontend AOT de Gram

La prueba AOT es opt-in porque requiere un parser C generado con Clang. El
parser solo produce GIR/AST; las pasadas semánticas y el backend LLVM siguen
siendo los de Bagron:

```text
python tools/build_aot_parser.py
vnma test tests_aggressive/test_aot.py
```

También puede usarse un ejecutable externo mediante `BAGRON_AOT_PARSER`. Si no
hay parser disponible, las pruebas AOT se omiten y la suite restante conserva
su comportamiento normal.

Cuando `build/aot/bagron_aot.exe` existe, `Compiler()` y la CLI usan AOT por
defecto. Usa `--python` para forzar el parser Python, por ejemplo al medir el
baseline:

```text
vnma run main.py --python examples/canon/_main.bg
```

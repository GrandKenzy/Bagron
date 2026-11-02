# Descriptores opaque con ABI nominal

Se añadió `opaque Nombre: void*` o `opaque Nombre: int32` para describir
handles nativos sin exponerlos como punteros o enteros. La representación se
conserva directamente en LLVM, mientras que la compatibilidad fuente exige el
nombre nominal exacto.

```bg
opaque WINDOWS_FILE_DESCRIPTOR: void*
opaque LINUX_FILE_DESCRIPTOR: int32
```

Los descriptores pueden aparecer como retornos, parámetros y variables
escalares; no aceptan punteros, arrays, desreferenciación, indexación ni
direcciones. El análisis mantiene `owned` para valores locales/retornos,
`borrowed` para parámetros y `closed` después de una llamada `close_*`.

Rutas principales: `core/frontend/syntax/items/opaque_decl.py`,
`core/frontend/tools/opaque.py`, `core/frontend/ownership.py`,
`core/backend/llvm/types.py` y `tests_aggressive/test_opaque_descriptors.py`.

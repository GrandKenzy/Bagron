# Ejemplos de Bagron

Estas muestras son independientes y cada una presenta una parte concreta del
lenguaje. No forman una aplicación completa: sirven para leer la sintaxis,
probar una característica y partir de ahí.

## Recorrido rápido

| Archivo | Tema |
| --- | --- |
| `01_basico.bg` | variables, constantes, funciones, operadores y condiciones |
| `02_tipos_y_arrays.bg` | tipos intrínsecos, `chain`, arrays y metadatos |
| `03_bucles.bg` | `for ran`, `for in`, `while`, `break`, `continue` y lógica |
| `04_agregados.bg` | `enum`, `struct`, `mold`, `flags` y layouts |
| `05_punteros.bg` | direcciones, desreferenciación, `Null` y `@unsafe` |
| `06_buffer.bg` | buffers dinámicos, concatenación, `Len_t` y `Del` |
| `07_clases.bg` | clases, métodos, herencia, `@static`, `@frozen` y hooks |
| `08_modulos/` | imports por namespace, alias y selección de símbolos |
| `09_preprocesador.bg` | cláusulas de destino y preprocesador condicional |
| `10_ffi_y_assembler.bg` | `opaque`, `extern` y `@assembler` (depende del destino) |

Todos los ejemplos, salvo el último, están pensados para compilarse sin
dependencias nativas adicionales. El último muestra una frontera de integración
y requiere un destino Windows x64 con las herramientas de Clang disponibles.

```powershell
bagron examples/01_basico.bg -o build/01_basico --execute
bagron examples/07_clases.bg -o build/07_clases --execute
bagron examples/08_modulos/main.bg -o build/08_modulos --execute
```

Los casos de sintaxis inválida no se mezclan con los programas ejecutables. Las
restricciones se explican en [`docs/es/`](../docs/es/index.md) y sus validaciones
automatizadas viven en `tests/`.

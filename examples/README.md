# Ejemplos pequeños de Bagron

Estos archivos son muestras independientes de sintaxis. Cada uno enseña una
familia concreta del lenguaje; no forman una aplicación grande.

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
| `09_preprocesador.bg` | cláusulas de target y preprocesador condicional |
| `10_ffi_y_assembler.bg` | `opaque`, `extern` y `@assembler` (dependiente del target) |

Los primeros ocho ejemplos están pensados para leerse y compilarse sin
dependencias nativas adicionales. El último muestra fronteras de integración:
requiere un target Windows x64 y las herramientas de Clang disponibles.

```powershell
vnma run main.py examples/01_basico.bg
vnma run main.py examples/07_clases.bg
vnma run main.py examples/08_modulos/main.bg
```

La sintaxis intencionadamente inválida no se mezcla con los programas
ejecutables; las restricciones se explican en `docs/es/` y se prueban en
`tests/`.

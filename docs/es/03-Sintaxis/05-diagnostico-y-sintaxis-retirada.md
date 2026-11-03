# Diagnóstico y sintaxis retirada

Los errores de frontend señalan el archivo y la línea del módulo que los
originó. El compilador valida declaraciones antes de los cuerpos para poder
detectar firmas incompatibles, privacidad y ciclos de imports.

## Errores frecuentes

- `func main()` dentro de una clase no es el entrypoint global.
- `int` y `uint` no existen; usa un ancho explícito.
- Un array de parámetros necesita `Len_t` y `Size_t` consecutivos.
- Un `while` necesita una condición `bool`.
- Un puntero recibido con procedencia desconocida solo se puede desreferenciar
  dentro de `@unsafe`.
- `@order_msb` solo se aplica a `flags`.

## Formas que ya no son alternativas

`global`, `extern "library":`, `package`, `package2`, los alias ASM antiguos y
`@order_lsb` no son aliases de compatibilidad. Si aparecen, se produce un
diagnóstico en vez de reinterpretarlos silenciosamente.

La suite que conserva estos contratos está en `tests/test_modules.py`,
`tests/test_preprocessor.py`, `tests/test_types.py` y `tests/test_functions.py`.

# Conversión `chain` a `char[]`

Se añadió la conversión unidireccional de un `chain` constante a un `char[]`.
En una inicialización explícita se infiere la capacidad incluyendo el byte NUL;
el resultado conserva almacenamiento mutable independiente del rodata.

En argumentos, una función que recibe `char[]`, `Len_t` y `Size_t` puede aceptar
un literal o variable `chain` constante. LLVM reserva una temporal local,
copia sus bytes, escribe el terminador y pasa la dirección junto con `Len_t`
(longitud más uno) y `Size_t` (uno). La temporal no se expone al frontend ni
puede cruzar un retorno puntero.

La conversión inversa `char[] -> chain` queda rechazada: `chain` solo acepta
otro `chain` y se mantiene como referencia constante a rodata.

Archivos principales: `core/frontend/tools/types/compatibility.py`,
`core/frontend/tools/types/calls.py`,
`core/backend/llvm/functions/expressions/conversions.py` y
`tests_aggressive/test_chain_char_array_conversion.py`.

# `chain` como rodata y lowering directo

## Cambio

`chain` conserva su ABI de puntero a bytes terminados en `NUL` más `Len_t`, pero
`prod` y `high` ya no reservan una copia local para cadenas constantes ni un
`i8**` temporal para parámetros `chain`. Ambos apuntan directamente al rodata
privado del módulo o al argumento LLVM recibido.

El pool de literales es compartido por globales y funciones, deduplica por bytes
y emite constantes privadas con `unnamed_addr`. Las variables globales nombradas
siguen siendo arrays `constant` para conservar la forma observable del IR.

## Seguridad

- `chain[index]` conserva la constancia del elemento.
- Un índice literal de una cadena conocida incluye el `NUL` en su rango válido y
  se rechaza si queda fuera, incluso en `@unsafe`.
- `$chain[index]` produce un puntero al elemento constante; no puede convertirse
  en `char*` mutable.
- No se añade `noalias`: dos cadenas pueden compartir el mismo rodata.
- `nonnull` sí se emite para parámetros `chain` optimizados. `llvmlite 0.50`
  no admite `readonly` como atributo de parámetro; marcar la función completa
  como `readonly` sería incorrecto para wrappers que escriben por Win32.

## Ejemplo

```bg
@unsafe
func first(text: chain, length: Len_t) char:
    return text[0]
```

En `prod`/`high`, `text` permanece como `i8*` SSA y no requiere `text.addr`.
`dev` conserva el almacenamiento explícito para facilitar la inspección del IR.

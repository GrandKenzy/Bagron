# 01. Estados de `buffer`

Un `buffer` local empieza como `owned`. `Del` libera su almacenamiento y lo
lleva a `dead`:

```bg
func main() int32:
    data: buffer[4] = 0
    data[0] = 7
    Del data
    return 0
```

Después de `Del data`, cualquier lectura, escritura, llamada o segundo `Del`
se rechaza durante el análisis. Un parámetro `buffer[]` es `borrowed`: la
función puede leerlo y modificarlo, pero no puede liberarlo.

```bg
func fill(data: buffer[], length: Len_t) void:
    if length > 0:
        data[0] = 1
    return
```

El ownership permanece en el llamador. `buffer` administra almacenamiento
dinámico; `byte[N]` es un array estático y sigue reglas distintas.

### Ramas condicionales y reconstrucción

Si un `buffer` se libera con `Del` solo en una rama de un condicional que
continúa, queda potencialmente liberado y no puede usarse después salvo que esa
rama termine (`return`, `break`, `continue` o llamada `Never`) o reconstruya el
buffer antes de salir (`data = 0`, `data = {1, 2, 3, 4}` o `data = left + right`
tras `Del data`):

```bg
func replace(flag: int32) int32:
    data: buffer[4] = 0
    if flag == 1:
        Del data
        data = {1, 2, 3, 4}
    data[0] = 7
    Del data
    return 0
```

### Fugas y `--strict-ownership`

Cuando un `buffer` o descriptor `opaque` local sale de su ámbito o de un
`return` sin haberse liberado ni transferido en todas las rutas, el compilador
emite una advertencia de fuga. Con `--strict-ownership`, esas fugas se rechazan
como error de compilación.

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

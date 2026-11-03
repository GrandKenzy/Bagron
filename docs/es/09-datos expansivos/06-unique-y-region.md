# 06. `unique` y `Region_t`

`Region_t` acompaña obligatoriamente a un parámetro `unique` y representa la
región exclusiva demostrada por el compilador:

```bg
func normalize(
    values: unique int32[],
    length: Len_t,
    element_size: Size_t,
    region: Region_t
) void:
    if length > 0:
        values[0] = 0
    return

func main() int32:
    values: int32[2] = {4, 8}
    normalize(values)
    return 0
```

`Region_t` se declara después de `Len_t` y `Size_t` y nunca aparece en la
llamada. El compilador comprueba que el origen sea almacenamiento local o un
parámetro `unique` ya válido.

Dos argumentos `unique` no pueden representar la misma región, y un argumento
ordinario tampoco puede entrar en una región marcada como exclusiva. Los
arrays ordinarios conservan sus reglas de aliasing; `unique` es una garantía
adicional, no una propiedad automática de todo array.

Para `unique buffer[]` solo se necesita `Len_t` y `Region_t`:

```bg
func clear(data: unique buffer[], length: Len_t, region: Region_t) void:
    if length > 0:
        data[0] = 0
    return
```

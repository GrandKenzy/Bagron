# Ownership estático y préstamos

## Índice

- [01. Estados de `buffer`](01-estados-de-buffer.md)
- [02. `unique` y `Region_t`](02-unique-y-region.md)
- [03. Descriptores `opaque`](03-opaque-y-cierre.md)
- [04. `@unsafe` y la frontera de punteros](04-unsafe-y-punteros.md)
- [05. Alcance real del borrow checker](05-alcance-del-borrow-checker.md)

Bagron no tiene un recolector de basura. La validación conserva estados
estáticos para `buffer` y descriptores `opaque`.

## Estados de `buffer`

```bg
func main() int32:
    data: buffer[4] = 0
    data[0] = 7
    Del data
    return 0
```

Un buffer local empieza como `owned`. `Del` lo lleva a `dead`; cualquier uso
posterior es un error de compilación. Un parámetro `buffer[]` es `borrowed`: se
puede leer y modificar, pero la función receptora no puede liberarlo.

```bg
func fill(data: buffer[], length: Len_t) void:
    if length > 0:
        data[0] = 1
    return
```

El ownership permanece en el llamador. `buffer` no es `byte[N]`: el primero usa
reserva dinámica; el segundo es un array estático.

## Exclusividad con `unique`

```bg
func transform(
    data: unique buffer[],
    length: Len_t,
    region: Region_t
) void:
    return
```

`Region_t` es oculto en la llamada y solo se acepta cuando el compilador puede
demostrar una procedencia exclusiva. El contrato también se aplica a arrays
`unique T[]`; no cambia las reglas de los punteros crudos.

`$value` obtiene una dirección, pero el puntero no mantiene vivo el objeto ni
puede retornarse desde una función. La implementación principal está en
`core/frontend/ownership.py`.

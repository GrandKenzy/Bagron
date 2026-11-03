# 02. `unique` y `Region_t`

`unique` declara un préstamo exclusivo para una región de almacenamiento:

```bg
func transform(
    data: unique buffer[],
    length: Len_t,
    region: Region_t
) void:
    if length > 0:
        data[0] = 1
    return
```

`Region_t` es un parámetro oculto en la llamada. El compilador lo acepta solo
cuando puede demostrar una procedencia concreta y exclusiva. Dos argumentos
`unique` no pueden representar la misma región.

La garantía es estática y no crea un objeto de ownership en runtime. Tampoco
se aplica a punteros crudos: obtener una dirección con `$value` no convierte
ese puntero en `unique` ni permite retornarlo desde una función.

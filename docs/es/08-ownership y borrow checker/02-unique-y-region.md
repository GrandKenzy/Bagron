# 02. `unique` y procedencia

`unique` declara un préstamo exclusivo para una región de almacenamiento:

```bg
func transform(
    data: unique buffer[]
) void:
    if data.<len> > 0:
        data[0] = 1
    return
```

La procedencia es metadata simbólica y no un parámetro fuente. El compilador
solo acepta la llamada cuando puede demostrar una procedencia concreta y exclusiva. Dos argumentos
`unique` no pueden representar la misma región.

La garantía es estática y no crea un objeto de ownership en runtime. Tampoco
se aplica a punteros crudos: obtener una dirección con `$value` no convierte
ese puntero en `unique` ni permite retornarlo desde una función.

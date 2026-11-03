# Calificadores de tipo

Bagron tiene dos calificadores de tipo principales: `const` y `unique`. Ambos
se escriben dentro de la forma del tipo y cambian qué operaciones son válidas.

## `const`

`const` protege el valor almacenado:

```bg
limit: const int32 = 10
text: const char[6] = "Hola"
```

Una asignación posterior a `limit` o a un elemento de `text` se rechaza. La
constancia del dato y la del puntero son independientes:

```bg
fixed *: const int32          # el dato apuntado no se modifica mediante fixed
const fixed_address *: int32  # la dirección guardada no cambia
const both *: const int32     # ambas propiedades
```

`const` no hace que el dato sea privado ni impide que otro acceso mutable
válido lo modifique. Solo controla el acceso descrito por esa declaración.

`chain` ya es constante y no puede declararse `const chain`. Los metadatos
`Len_t`, `Size_t`, `Signed_t` y `Region_t` tampoco aceptan `const`: el
compilador los suministra o controla internamente.

## `unique`

`unique` solo se permite en parámetros de arrays y `buffer`:

```bg
func normalize(
    values: unique int32[],
    length: Len_t,
    size: Size_t,
    region: Region_t
) void:
    if length > 0:
        values[0] = 0
    return
```

La llamada visible es `normalize(values)`. Bagron debe demostrar que el
argumento tiene una región de almacenamiento concreta y que no se solapa con
otra región `unique`. `Region_t` acompaña al parámetro y no se escribe en la
llamada.

No uses `unique` en escalares, punteros crudos, `chain` o metadatos. No
transfiere por sí solo ownership y no convierte una dirección obtenida con `$`
en una región exclusiva.

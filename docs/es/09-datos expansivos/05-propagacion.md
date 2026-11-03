# 05. Propagación entre funciones

Una función intermediaria puede recibir metadatos y reenviarlos sin que el
llamador los escriba otra vez:

```bg
func sink(values: int32[], length: Len_t, element_size: Size_t) usize:
    return length + element_size

func forward(values: int32[], length: Len_t, element_size: Size_t) usize:
    return sink(values)

func main() int32:
    values: int32[2] = {10, 20}
    forward(values)
    return 0
```

La expansión de `forward(values)` se asocia con `values` y queda disponible
para `sink(values)`. Esto evita recalcular o exponer manualmente la longitud y
el tamaño en cada capa de una API.

La asociación depende del nombre y del orden de la firma: `Len_t` y `Size_t`
deben seguir a su parámetro de datos. No intentes pasar `length` o
`element_size` como argumentos visibles; la llamada los rechaza por tener
parámetros compiler-supplied.

La misma regla permite reenviar `Len_t` de un `chain` o `buffer[]` y
`Region_t` de un parámetro `unique`, siempre que la función intermediaria
conserve el contrato de la firma.

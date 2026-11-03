# 02. Arrays y matrices

Un parámetro array requiere `Len_t` y `Size_t` inmediatamente después del
array, en ese orden:

```bg
func sum(values: int32[], length: Len_t, element_size: Size_t) int32:
    total: int32 = 0
    for index: usize in values:
        total += values[index]
    return total
```

En una llamada `sum(values)`, `Len_t` es la primera dimensión y `Size_t` es
el tamaño en bytes de un elemento de esa dimensión. Para `int32[3]` los valores
son `3` y `4`.

Las matrices conservan toda su forma y tienen como máximo tres dimensiones:

```bg
func inspect(matrix: int16[2][3][4], depth: Len_t, block_size: Size_t) usize:
    return depth + block_size

func main() int32:
    matrix: int16[2][3][4] = 0
    inspect(matrix)
    return 0
```

Aquí `depth = 2` y `block_size = 24`: cada elemento exterior es un bloque
`int16[3][4]` de 24 bytes. La función debe declarar la forma exacta; un
`int16[2][4]` no puede pasarse donde se espera `int16[2][3]`.

Un array abierto (`T[]`) necesita que su longitud sea conocida en la llamada o
que se propague desde otro parámetro expansivo. `@unsafe` no elimina esta
obligación.

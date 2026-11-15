# 02. Arrays y matrices

`.<len>` devuelve la primera dimensión del array y `.<size>` devuelve el
tamaño en bytes de un elemento exterior:

```bg
func sum(values: int32[]) int32:
    total: int32 = 0
    for index: usize in values:
        total += values[index]
    return total

func inspect(matrix: int16[2][3][4]) usize:
    return matrix.<len> + matrix.<size>
```

Para `int16[2][3][4]`, los resultados son `2` y `24`: cada elemento exterior
es un bloque `int16[3][4]`. Las matrices conservan su forma exacta y admiten
hasta tres dimensiones. Un `int16[2][4]` no puede pasarse donde se espera
`int16[2][3]`.

Los arrays abiertos (`T[]`) reciben automáticamente la longitud necesaria en
el ABI. `@unsafe` no cambia la forma ni la compatibilidad del array.

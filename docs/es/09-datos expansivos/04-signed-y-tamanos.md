# 04. `Signed_t` y tamaños

`Signed_t` es opcional y debe ir después de `Len_t` y `Size_t` cuando se usa
con un array:

```bg
func classify(
    values: int32[],
    length: Len_t,
    element_size: Size_t,
    signed: Signed_t
) int32:
    if signed == 0:
        return 1
    return 0
```

El compilador suministra `0` para tipos signed y `1` para tipos unsigned o
`byte`. En una matriz, el indicador describe el tipo de los elementos, no cada
dimensión.

`Size_t` también puede solicitarse para un escalar:

```bg
func bytes_of(value: int32, size: Size_t) usize:
    return size
```

En ese caso el tamaño es el de `int32`. No declares `Len_t` para un escalar:
la longitud solo pertenece a `array`, `buffer[]` o `chain`.

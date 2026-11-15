# 04. Tamaños

La API actual no usa `Len_t`, `Size_t` ni `Signed_t` en las firmas. El tamaño
se consulta en el valor que lo origina:

```bg
func bytes_of(value: int32) usize:
    return value.<size>

func element_bytes(values: uint16[4][3]) usize:
    return values.<size>
```

`.<size>` devuelve el tamaño ABI del escalar. En una matriz devuelve el tamaño
del elemento de la primera dimensión; en el ejemplo de `uint16[4][3]` es `6`.
Los tipos enteros definidos por `#defint` y `#defuint` siguen las reglas de
tamaño de LLVM.

La signedness ya pertenece al tipo. No hace falta transportarla como un valor
auxiliar.

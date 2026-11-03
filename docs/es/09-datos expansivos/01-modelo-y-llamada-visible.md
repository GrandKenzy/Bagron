# 01. Modelo y llamada visible

Un dato expansivo es un valor que el compilador obtiene de otro argumento y
añade a la firma real. Se declara en la función para que el cuerpo pueda
usarlo, pero no se escribe en la llamada:

```bg
func inspect(
    values: int32[],
    length: Len_t,
    element_size: Size_t
) usize:
    return length + element_size

func main() int32:
    values: int32[3] = {1, 2, 3}
    inspect(values)
    return 0
```

La llamada fuente tiene un solo argumento. El compilador calcula `length = 3`
y `element_size = 4` y los pasa según el ABI de la función.

Los tipos expansivos son:

- `Len_t`: longitud de una dimensión o de un dato contable;
- `Size_t`: tamaño en bytes de un elemento exterior;
- `Signed_t`: indicador de signedness, `0` o `1`;
- `Region_t`: procedencia exclusiva de un parámetro `unique`.

Son parámetros de metadatos, no valores que el llamador pueda proporcionar
manualmente. Tampoco son tipos intercambiables con `usize`, `uint64` u otro
entero normal.

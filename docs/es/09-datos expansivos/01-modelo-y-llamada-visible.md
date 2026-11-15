# 01. Modelo y llamada visible

Los datos derivados se consultan desde el valor que los origina. No se
declaran parámetros auxiliares ni se escriben argumentos ocultos en las
llamadas:

```bg
func inspect(values: int32[]) usize:
    return values.<len> * values.<size>

func main() int32:
    values: int32[3] = {1, 2, 3}
    total: usize = inspect(values)
    return 0
```

La llamada visible solo contiene `values`. El compilador añade al ABI la
metadata que el cuerpo necesita, sin exponerla al usuario ni convertirla en
parte de la firma fuente.

Los miembros válidos son `.<len>` para longitudes, `.<size>` para tamaños y
`.<region>` para consultar procedencia conocida de un préstamo `unique`.
Son de solo lectura y no pueden reasignarse como campos normales.

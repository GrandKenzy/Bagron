# 05. Propagación entre funciones

Si una función intermedia reenvía un array abierto o un `chain` a otra función,
el compilador conserva la metadata necesaria sin que el usuario la declare:

```bg
func sink(values: int32[]) usize:
    return values.<len>

func forward(values: int32[]) usize:
    return sink(values)

func main() int32:
    values: int32[2] = {10, 20}
    count: usize = forward(values)
    return 0
```

La información se asocia al valor fuente y sigue el recorrido de la llamada.
No se deben añadir parámetros de longitud, tamaño, signedness o región para
simular esta propagación.

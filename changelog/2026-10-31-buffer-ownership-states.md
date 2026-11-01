# Estados estáticos de ownership para `buffer`

Bagron incorpora un análisis de ownership de coste cero en ejecución para los
buffers dinámicos. Cada binding de `buffer` se clasifica como `owned`,
`borrowed` o `dead` únicamente durante la compilación.

```bg
func consume(data: buffer[], length: Len_t) void:
    ; data es borrowed: puede usarse, pero no liberarse
    return

func main() int32:
    data: buffer[4] = 0 ; owned
    Del data             ; dead
    ; data[0] = 1        ; error: uso después de Del
    return 0
```

El compilador rechaza la doble liberación, el uso posterior a `Del` y la
liberación de parámetros prestados. El estado se conserva solo como metadato
del frontend; no añade campos al descriptor, llamadas de runtime ni cambios al
ABI o al backend LLVM. En ramas y bucles se usa una unión conservadora: si una
ruta puede producir `dead`, el uso posterior se rechaza; `Del` dentro de un
bucle también se rechaza para evitar una doble liberación en iteraciones
posteriores.

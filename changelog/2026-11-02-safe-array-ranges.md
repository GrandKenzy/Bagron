# Rangos seguros para arrays abiertos

Las funciones seguras pueden demostrar índices dinámicos de `char[]`, `byte[]`
y otros arrays cuando un `Len_t` asociado los limita:

```bg
func fill(data: char[], length: Len_t, size: Size_t) void:
    index: usize = 0
    while index < length:
        data[index] = "X"
        index += 1
    return
```

La prueba es local al `while`, `for` o rama `if` que establece la condición.
El compilador solo conserva el hecho mientras el índice no se actualice antes
de un acceso posterior. Los índices dinámicos sin una prueba suficiente y los
punteros crudos siguen requiriendo `@unsafe`. No se añade metadata ni coste de
runtime: el backend LLVM recibe el mismo array y los mismos expansivos ABI.

La cobertura está en `tests_aggressive/test_safe_array_ranges.py`; las pruebas
del backend mantienen además la comprobación de límites cuando no existe una
prueba estática.

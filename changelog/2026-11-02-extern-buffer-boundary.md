# Frontera ABI de `buffer`

Los punteros derivados de un `buffer` administrado ya no pueden pasarse a una
función `extern`, incluso desde una función `@unsafe`:

```bg
extern c "ucrt":
    free(pointer *: void) void

@unsafe
func invalid() void:
    data: buffer[4096] = 0
    free($data[0]) ; error
    return
```

La validación usa procedencia estática, no añade estados `escaped` ni
anotaciones ABI. Las funciones Bagron siguen recibiendo `buffer[]`; los
punteros crudos y las direcciones explícitas de arrays fijos continúan
disponibles para APIs externas como `WriteFile` dentro de `@unsafe`. Los
retornos opacos como `void*` de Windows permanecen permitidos.

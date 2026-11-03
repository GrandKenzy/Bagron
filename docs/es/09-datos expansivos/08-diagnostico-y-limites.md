# 08. Diagnóstico y límites

Estas firmas son inválidas:

```bg
func missing_size(values: int32[], length: Len_t) void:
    return

func wrong_order(values: int32[], size: Size_t, length: Len_t) void:
    return

func buffer_size(data: buffer[], length: Len_t, size: Size_t) void:
    return
```

Un array exige `Len_t` y `Size_t`, en ese orden. `Signed_t` debe ir después de
ambos y `Region_t` solo puede seguir a un parámetro `unique`. Un `buffer` solo
acepta `Len_t`.

También se rechazan estas llamadas:

```bg
func consume(values: int32[], length: Len_t, size: Size_t) void:
    return

func bad() int32:
    values: int32[2] = {1, 2}
    consume(values, 2, 4)  # los metadatos no son argumentos visibles
    return 0
```

Un array abierto necesita una longitud conocida o propagada. Una matriz debe
conservar su forma exacta y no puede exceder tres dimensiones. `@unsafe` no
permite omitir metadatos, cambiar la forma del array ni fabricar un
`Region_t`.

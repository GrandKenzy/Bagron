# 03. `chain` y `buffer`

`chain` representa texto constante y puede pedir solo `Len_t`:

```bg
func print_text(text: chain, length: Len_t) void:
    return

func main() int32:
    print_text("Hola")
    return 0
```

La longitud incluye el byte `NUL`. Para el literal `"Hola"`, `Len_t` vale `5`.
Un `chain` no puede declararse como puntero y el compilador solo puede calcular
su longitud directamente cuando el valor es constante o cuando la expansión
ya fue propagada.

`buffer[]` también usa solo `Len_t`, tomado del descriptor:

```bg
func fill(data: buffer[], length: Len_t) void:
    if length > 0:
        data[0] = 1
    return
```

`Size_t` no aplica a `buffer`: el descriptor representa unidades de byte y el
tamaño sería siempre `1`. Un buffer tampoco se convierte silenciosamente en un
array o en un puntero crudo.

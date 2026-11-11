# 03. `chain` y `buffer`

`chain` representa texto constante como bytes UTF-8 terminados en `NUL` y puede
pedir solo `Len_t`:

```bg
func print_text(text: chain, length: Len_t) void:
    return

func main() int32:
    print_text("Hola")
    return 0
```

La longitud cuenta bytes e incluye el byte `NUL`; no cuenta caracteres Unicode.
Para el literal `"Hola"`, `Len_t` vale `5`. Para un literal con caracteres
acentuados, `Len_t` aumenta según su representación UTF-8.
De forma similar, cuando un literal de texto se pasa como `char[]`, el valor
`Len_t` sintetizado por el compilador representa la capacidad total del buffer
incluyendo el terminador `NUL`. Las funciones de procesamiento de texto o de
formateo en librerías deben iterar hasta el primer byte `\0` o `length` para
determinar la longitud lógica del contenido.
Un `chain` no puede declararse como puntero y el compilador solo puede calcular
su longitud directamente cuando el valor es constante o cuando la expansión
ya fue propagada.

`buffer[]` también usa solo `Len_t`, tomado de la capacidad del descriptor:

```bg
func fill(data: buffer[], length: Len_t) void:
    if length > 0:
        data[0] = 1
    return
```

`Size_t` no aplica a `buffer`: el descriptor representa unidades de byte y el
tamaño de cada unidad es `1`. Un buffer tampoco se convierte silenciosamente
en un array, un `chain` o un puntero crudo.

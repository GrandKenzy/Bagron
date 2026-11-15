# 03. `chain` y `buffer`

`chain` representa texto UTF-8 terminado en `NUL`. Su `.<len>` cuenta bytes e
incluye el terminador:

```bg
func print_text(text: chain) usize:
    return text.<len>

func main() int32:
    count: usize = print_text("Hola")
    return 0
```

Para `"Hola"`, la longitud es `5`. Los caracteres Unicode ocupan la cantidad
de bytes que indique UTF-8, no necesariamente un byte por carácter.

`buffer[]` obtiene `.<len>` desde su descriptor. `.<size>` no aplica a un
buffer porque sus unidades son bytes:

```bg
func fill(data: buffer[]) void:
    if data.<len> > 0:
        data[0] = 1
```

Un buffer no se convierte silenciosamente en un array, un `chain` ni un
puntero crudo.

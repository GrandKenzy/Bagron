# Contrato de retornos de funciones

Las funciones de Bagron solo pueden retornar:

- intrínsecos escalares y `chain` inmutable;
- valores agregados por copia (`struct`, `mold`, `flags` y `class`);
- `void` o `Never` como formas de control.

Arrays, `buffer` y punteros quedan fuera de los retornos de funciones de
Bagron. Los buffers continúan siendo préstamos de entrada: la función puede
rellenarlos, pero la responsabilidad de liberar el almacenamiento permanece en
el llamador. Las declaraciones `extern` conservan su validador ABI independiente
para poder describir punteros de APIs nativas.

```bg
func fill(data: buffer[], length: Len_t) void:
    data[0] = 42
    return

struct Point:
    value: int32

func echo(value: Point) Point:
    return value
```

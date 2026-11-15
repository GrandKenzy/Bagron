# Arrays

Un array es un bloque contiguo de elementos. Su forma pertenece al tipo:
`int32[3]` y `int32[4]` son tipos distintos.

## Declaración

```bg
values: int32[3] = {1, 2, 3}
inferred: int32[] = {4, 5, 6}
matrix: int32[2][3] = {{1, 2, 3}, {4, 5, 6}}
```

Los arrays fijos no inicializados empiezan en cero. Las matrices son
rectangulares, estáticas y admiten hasta tres dimensiones; todas sus
dimensiones deben conocerse.

## Parámetros y forma

Los arrays de parámetros se pasan por referencia y conservan su forma. La
llamada no necesita parámetros auxiliares:

```bg
func sum(values: int32[]) int32:
    total: int32 = 0
    for index: usize in values:
        total += values[index]
    return total
```

Un `int32[2][3]` solo acepta otro `int32[2][3]`; no se convierte en
`int32[2][4]`. Un array abierto (`T[]`) sigue siendo una vista del
almacenamiento del llamador, no una reserva dinámica.

## Miembros `.<len>` y `.<size>`

```bg
func describe(matrix: int16[2][3][4]) usize:
    return matrix.<len> + matrix.<size>
```

En este caso `.<len>` vale `2` y `.<size>` vale `24`, porque el elemento
exterior es `int16[3][4]`. El tamaño total puede expresarse como
`matrix.<len> * matrix.<size>`.

Para recorrer un array, `for index in values` demuestra el límite de la
primera dimensión. También puede usarse una condición explícita sobre
`values.<len>` en código seguro:

```bg
func read(values: int32[], index: usize) int32:
    if index < values.<len>:
        return values[index]
    return 0
```

Un índice que no pueda demostrarse requiere `@unsafe`. La garantía de un
array no se transfiere a otro array ni a un puntero.

## `char[]` y `chain`

```bg
text: chain = "Hola"
buffer: char[] = text
buffer[0] = "X"
```

La copia mutable conserva el terminador `NUL`. Un `chain` no se convierte
implícitamente en un puntero ni en un array que escape de la llamada.

Los miembros del compilador son de solo lectura y se distinguen de los campos
normales por los delimitadores angulares. `value.len` no es equivalente a
`value.<len>`.

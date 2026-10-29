# Arrays

Un array es un bloque contiguo de elementos del mismo tipo. Su tamaño forma
parte del tipo: `int32[3]` y `int32[4]` no son el mismo array, aunque ambos
contengan enteros de 32 bits.

Los arrays son útiles para representar buffers, tablas, cadenas de caracteres,
matrices y bloques de datos que deben conservar un layout predecible en
memoria.

## Cómo se crean

### Tamaño explícito

El tamaño se escribe después del tipo entre corchetes:

```bg
values: int32[3] = {1, 2, 3}
buffer: byte[8]
```

`int32[3]` contiene exactamente tres elementos. Si un array de tamaño fijo no
recibe un inicializador, sus elementos comienzan con el valor cero.

El tamaño debe ser mayor que cero. `int32[0]` no es un array válido.

### Tamaño inferido

Unos corchetes vacíos indican que el compilador debe inferir el tamaño a partir
del inicializador:

```bg
values: int32[] = {1, 2, 3} ; se convierte en int32[3]
letters: char[] = "Hola"   ; se convierte en char[5]
```

Un array sin tamaño explícito necesita un inicializador. El compilador no puede
reservar `int32[]` sin saber cuántos elementos debe contener.

### Inicializadores parciales

Un inicializador puede proporcionar menos elementos que el tamaño declarado.
Los elementos restantes se rellenan con cero:

```bg
values: int32[5] = {10, 20} ; {10, 20, 0, 0, 0}
```

Si el inicializador excede el tamaño declarado, el compilador rechaza la
declaración. Bagron no trunca elementos ni los descarta silenciosamente.

### Arrays multidimensionales

Se pueden declarar varias dimensiones:

```bg
matrix: int32[2][3] = {
    {1, 2, 3},
    {4, 5, 6}
}
```

Este tipo contiene dos filas y cada fila contiene tres valores `int32`. La
primera dimensión es la cantidad de elementos exteriores; la última dimensión
describe el elemento más interno.

## Acceso y seguridad

Los elementos se acceden con un índice:

```bg
values: int32[3] = {10, 20, 30}
first: int32 = values[0]
values[1] = 25
```

En una función segura, el índice debe ser conocido durante la compilación y
estar dentro del rango demostrado del array:

```bg
func read(values: int32[3], length: Len_t, element_size: Size_t) int32:
    return values[1]
```

Un índice dinámico requiere que la función esté marcada como `@unsafe`, porque
el compilador ya no puede demostrar en compilación que el acceso está dentro
del bloque reservado:

```bg
@unsafe
func read_at(
    values: int32[],
    length: Len_t,
    element_size: Size_t,
    index: usize
) int32:
    return values[index]
```

Un índice literal fuera de rango siempre es un error. `chain` tiene una regla
aún más estricta: indexarlo también requiere `@unsafe`, porque es una cadena
estática y constante, no un buffer mutable ordinario.

Para obtener la dirección de un elemento se usa `$` sobre el acceso:

```bg
values: int32[3] = {1, 2, 3}
element *: int32 = $values[0]
```

La dirección del array completo no se inventa como si fuera un elemento; se
debe indicar qué elemento se desea direccionar.

## `char[]` y `chain`

Ambos pueden representar texto, pero no tienen la misma semántica.

| Característica | `char[]` | `chain` |
|:---|:---|:---|
| Naturaleza | Array ordinario de `char`. | Cadena estática especial. |
| Mutabilidad | Mutable, salvo que use `const`. | Inmutable por definición. |
| Tamaño | Puede declararse, inferirse o rellenarse. | Se calcula a partir del literal. |
| Terminación | Solo se reserva `NUL` al inicializar desde un literal de cadena. | Siempre incluye `NUL`. |
| Arrays o punteros | Puede combinarse con arrays y punteros según el tipo. | No puede combinarse con arrays ni punteros. |
| Indexación | Segura con índice demostrable; dinámica en `@unsafe`. | Siempre requiere `@unsafe`. |

`char` representa un carácter ASCII. `chain` representa almacenamiento de
caracteres ASCII terminado en `NUL`, donde `NUL` es el byte cero (`0`) que
marca el final de la cadena.

### El `NUL` adicional

Cuando un literal se asigna a un array de `char`, el compilador necesita un
elemento adicional para guardar el terminador:

```bg
name: char[5] = "Hola" ; H, o, l, a, NUL
```

Por eso `char[4] = "Hola"` es inválido: no queda espacio para `NUL`.

Si el array es más grande, el `NUL` sigue ocupando un elemento y el espacio
restante se rellena con cero:

```bg
name: char[8] = "Hola" ; H, o, l, a, NUL, 0, 0, 0
```

El tamaño de `char[]` también cuenta ese elemento:

```bg
name: char[] = "Hola" ; el compilador infiere char[5]
```

`byte[]` no tiene un contrato textual de terminación. Sus elementos son datos
crudos y el cero no tiene un significado especial:

```bg
raw: byte[4] = "Hola" ; cuatro bytes: H, o, l, a
```

Un `byte[5]` inicializado con el mismo literal puede tener un cero de relleno,
pero ese cero no convierte al array en una cadena terminada en `NUL`. La
terminación es una regla de `char` y `chain`, no de `byte`.

## `const` en arrays

`const` se aplica al tipo del array y protege todos sus elementos:

```bg
name: const char[5] = "Hola"
numbers: const int32[3] = {1, 2, 3}
```

Leer estos arrays es válido, pero modificar un elemento es un error:

```bg
name[0] = "X"       ; error: array constante
numbers[1] = 10     ; error: array constante
```

Un array de `char` mutable puede inicializarse desde un literal y después
editarse. Esa mutabilidad es la diferencia principal frente a `chain`:

```bg
buffer: char[6] = "Hola"
buffer[0] = "h"     ; válido

text: chain = "Hola"
; text[0] = "h"     ; no permitido: chain es inmutable
```

No se puede escribir `const chain`: `chain` ya es inmutable y declarar la
constancia otra vez es redundante e inválido.

## Expansión de `Len_t` y `Size_t`

`Len_t` y `Size_t` son metatipos expansivos de compilación. El usuario los
escribe en la firma de una función, pero no los proporciona en la llamada.
Bagron calcula sus argumentos ocultos a partir del dato inmediatamente
anterior.

### Regla obligatoria en firmas

Toda función que reciba un array debe declarar, inmediatamente después del
array, un bloque formado por `Len_t` y `Size_t`, siempre en ese orden:

```bg
func consume(data: int32[], length: Len_t, element_size: Size_t) void:
    return
```

La regla se aplica tanto a arrays con tamaño inferido (`int32[]`) como a arrays
con tamaño explícito (`int32[3]`). En ambos casos los metadatos son ocultos en
la llamada:

```bg
values: int32[3] = {1, 2, 3}
consume(values) ; expansión interna: consume(values, 3, 4)
```

Estas firmas son inválidas:

```bg
func missing(data: int32[]) void:                         ; faltan ambos
    return
func only_length(data: int32[], length: Len_t) void:      ; falta Size_t
    return
func reversed(data: int32[], size: Size_t, length: Len_t) void:
    return                                                     ; orden inválido
```

La obligación también se aplica a funciones `@unsafe`. `@unsafe` permite
accesos dinámicos, pero no convierte el array en dinámico ni permite eliminar
sus metadatos. Un parámetro `T[]` representa una vista ABI de un array estático
recibido desde el llamador; puede reenviar los metadatos que recibió a otra
función:

```bg
func forward(data: int32[], length: Len_t, element_size: Size_t) void:
    consume(data) ; reenvía length y element_size
    return
```

`chain` no es un array ordinario y conserva su excepción: puede usar `Len_t`
para su longitud estática y terminador `NUL`, pero no está obligado a declarar
`Size_t`.

### `Len_t`: cantidad de elementos

`Len_t` funciona con arrays y con `chain` estático:

- en un array, es la cantidad de elementos de la primera dimensión;
- en un `chain`, incluye el `NUL` final;
- en un array de `char` inicializado con texto, incluye el espacio del `NUL`;
- conserva el tamaño declarado aunque el texto inicial sea más corto.

```bg
name: char[16] = "Hola"

func print_name(data: char[], length: Len_t, element_size: Size_t) void:
    return

print_name(name) ; expansión interna: print_name(name, 16, 1)
```

En un array multidimensional, `Len_t` representa la dimensión exterior:

```bg
matrix: int32[2][3] = {{1, 2, 3}, {4, 5, 6}}

func send_rows(data: int32[][], rows: Len_t, row_size: Size_t) void:
    return

send_rows(matrix) ; expansión interna: send_rows(matrix, 2, 12)
```

`Len_t` requiere que el tamaño relevante sea conocido en compilación. En una
llamada, el array concreto debe tener una longitud demostrable; un parámetro
`T[]` puede reenviar el `Len_t` que recibió de otra función. No puede obtenerse
de un puntero crudo.

### `Size_t`: tamaño en bytes del elemento o tipo

`Size_t` no cuenta elementos. Indica cuántos bytes ocupa el tipo asociado:

| Fuente | `Len_t` | `Size_t` | Tamaño total |
|:---|---:|---:|---:|
| `int32[3]` | `3` | `4` | `12` |
| `char[5]` | `5` | `1` | `5` |
| `byte[3]` | `3` | `1` | `3` |
| `int32[2][3]` | `2` | `12` | `24` |

Para un array, `Size_t` es el tamaño de un solo elemento de la primera
dimensión. Por eso, en `int32[2][3]`, cada elemento exterior es una fila de
tres `int32` y ocupa `12` bytes.

El tamaño total se obtiene multiplicando ambos metadatos:

```text
tamaño total del array = Len_t * Size_t
```

En un escalar, `Size_t` representa el tamaño completo del escalar. En un
puntero, representa el tamaño del puntero del target. Para un `chain` estático,
su almacenamiento está compuesto por caracteres de un byte e incluye el
`NUL` final.

### Varios metatipos en una firma

Para cada parámetro de array, `Len_t` y `Size_t` son obligatorios. Deben
aparecer como un bloque consecutivo después del array, siempre en el orden
`Len_t` y luego `Size_t`; después pueden solicitarse metadatos de otros
parámetros:

```bg
values: int32[3] = {1, 2, 3}
other: byte[8]

func send(
    data: int32[],
    length: Len_t,
    element_size: Size_t,
    raw: byte[],
    raw_length: Len_t,
    raw_size: Size_t
) void:
    return

send(values, other)
; expansión interna:
; send(values, 3, 4, other, 8, 1)
```

El llamador solo escribe los argumentos visibles. No puede insertar, sustituir
ni calcular manualmente `Len_t` o `Size_t`.


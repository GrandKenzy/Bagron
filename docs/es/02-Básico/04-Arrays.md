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

### Inicializadores parciales de arrays simples

En un array simple de una dimensión, un inicializador puede proporcionar menos
elementos que el tamaño declarado. Los elementos restantes se rellenan con
cero:

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

Una matriz de Bagron es rectangular y estática: todas sus dimensiones forman
parte del tipo. No se permiten dimensiones abiertas o parcialmente conocidas.
Bagron admite como máximo tres dimensiones (`1D`, `2D` y `3D`).
En una firma de función, por tanto, estas formas son inválidas como
parámetros:

```bg
func bad_a(data: int32[][], rows: Len_t, row_size: Size_t) void:
    return

func bad_b(data: int32[][3], rows: Len_t, row_size: Size_t) void:
    return

func bad_c(data: int32[2][], rows: Len_t, row_size: Size_t) void:
    return
```

La forma válida declara todas las filas y profundidades:

```bg
func process(
    data: int32[2][3],
    rows: Len_t,
    row_size: Size_t
) void:
    return
```

Una matriz `T[R][C]` solo acepta otra matriz con exactamente `R` filas y `C`
columnas. La regla se aplica a cada profundidad: `int32[2][3]` no acepta
`int32[2][4]`, `int32[3][3]` ni una matriz abierta. No existen conversiones
entre matrices con formas distintas.

### Paso por referencia

Todos los arrays de parámetros se pasan por referencia, tanto los abiertos
unidimensionales como los de tamaño fijo y las matrices. El almacenamiento
local conserva el tipo completo, mientras que el parámetro recibe una
dirección a ese almacenamiento:

```text
int32[3]       -> [3 x i32]*
int32[2][3]    -> [2 x [3 x i32]]*
int32[2][3][4] -> [2 x [3 x [4 x i32]]]*
```

Una escritura dentro de la función modifica la variable original. No se crean
copias silenciosas. Por esa razón, el argumento debe ser una variable de array
con almacenamiento propio; los literales y temporales no pueden pasarse a un
parámetro de array.

La forma también se valida en cada llamada y los metadatos ocultos permanecen
asociados a su array aunque los arrays cambien de posición en firmas
anidadas.

### Inicialización rectangular de matrices

El inicializador de una matriz debe tener exactamente la forma declarada. Cada
fila, submatriz y profundidad debe estar completa y tener la misma longitud:

```bg
matrix: int32[2][3] = {
    {1, 2, 3},
    {4, 5, 6}
}
```

Se rechazan filas cortas, filas largas, filas de longitudes diferentes y
profundidades incompletas. El relleno implícito con cero solo está disponible
para arrays simples de una dimensión; no se aplica a matrices.

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

Para recorrer un array fijo sin repetir manualmente su tamaño, la forma
canónica es `for i: int32 in values:`. El compilador inserta la longitud exacta
de la primera dimensión como límite exclusivo y puede demostrar que
`values[i]` está dentro del array cuando el acceso usa ese mismo origen:

```bg
func sum(values: int32[3], length: Len_t, element_size: Size_t) int32:
    total: int32 = 0
    for i: int32 in values:
        total += values[i]
    return total
```

La garantía no se transfiere a otro array ni a un puntero. Para un array abierto
el límite procede de `Len_t`; si el compilador no puede probar estáticamente el
acceso, se requiere `@unsafe` como en cualquier otro índice dinámico.

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

El acceso a una matriz sigue la misma regla en cada profundidad. Los índices
literales se comprueban contra todas las dimensiones conocidas; un índice
dinámico en cualquier profundidad requiere `@unsafe`.

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

En parámetros, `const` es estrictamente covariante:

- un array mutable puede pasarse a un parámetro `const`;
- un array `const` puede pasarse a un parámetro `const`;
- un array `const` no puede pasarse a un parámetro mutable.

La forma y la constancia se comprueban juntas; `const` no permite convertir una
matriz en otra forma ni elimina la comprobación de sus dimensiones.

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
`Size_t`. `buffer` tampoco es un array estático: su descriptor incluye la
capacidad en bytes y sus funciones deben declarar solo `Len_t`:

```bg
func inspect(data: buffer[], length: Len_t) usize:
    return length

raw: buffer[32] = 0
inspect(raw) ; expansión interna: inspect(raw, 32)
```

### `Len_t`: cantidad de elementos

`Len_t` funciona con arrays, `buffer` y con `chain` estático:

- en un array, es la cantidad de elementos de la primera dimensión;
- en un `buffer`, es su longitud en bytes;
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

func send_rows(data: int32[2][3], rows: Len_t, row_size: Size_t) void:
    return

send_rows(matrix) ; expansión interna: send_rows(matrix, 2, 12)
```

En una matriz 3D solo se expande la dimensión exterior. Las dimensiones
interiores permanecen codificadas en el tipo:

```bg
values: int32[2][3][4]

func send_blocks(
    data: int32[2][3][4],
    blocks: Len_t,
    block_size: Size_t
) void:
    return

send_blocks(values) ; expansión interna: send_blocks(values, 2, 48)
```

No se añade un metadato por cada profundidad. La profundidad completa, sus
filas y sus columnas se verifican mediante el tipo estático.

Al reenviar una matriz entre funciones, el compilador conserva ese tipo
completo y pasa un puntero al mismo array completo. `Len_t` y `Size_t` solo
aportan los valores numéricos ocultos; no se usan para reconstruir la forma.
Por eso una función que recibe `int32[2][3][4]` no puede reenviarlo a una
función que espere otra profundidad o una fila distinta.

`Len_t` requiere que el tamaño relevante sea conocido en compilación. En una
llamada, el array concreto debe tener una longitud demostrable; un parámetro
`T[]` puede reenviar el `Len_t` que recibió de otra función. No puede obtenerse
de un puntero crudo. Un parámetro `buffer[]` puede reenviar el `Len_t` que
recibió o extraerlo del descriptor del buffer concreto.

### `Size_t`: ancho exterior en bytes

`Size_t` no cuenta elementos ni profundidades. Indica el ancho en bytes de una
unidad exterior del dato: el tipo que queda dentro de la primera pareja de
corchetes. Esta regla es única para cualquier profundidad:

```text
Size_t(T[N1])          = tamaño(T)
Size_t(T[N1][N2])      = tamaño(T[N2])
Size_t(T[N1][N2][N3])  = tamaño(T[N2][N3])
```

Por eso, en una matriz `int32[2][3]`, una unidad exterior es una fila de tres
`int32` y mide `12` bytes. En `int32[2][3][4]`, una unidad exterior es un
bloque `int32[3][4]` y mide `48` bytes. `Size_t` no cambia de significado:
siempre es el ancho de la unidad exterior.

| Fuente | `Len_t` | `Size_t` | Tamaño total |
|:---|---:|---:|---:|
| `int32[3]` | `3` | `4` | `12` |
| `char[5]` | `5` | `1` | `5` |
| `byte[3]` | `3` | `1` | `3` |
| `int32[2][3]` | `2` | `12` | `24` |
| `int32[2][3][4]` | `2` | `48` | `96` |

El tamaño del elemento base se conserva en el tipo, pero no sustituye al
ancho exterior de una matriz. Las filas, bloques y profundidades interiores
no se envían como metadatos independientes porque ya están fijados por el
tipo estático.

El tamaño total se obtiene multiplicando ambos metadatos:

```text
tamaño total del array = Len_t * Size_t
```

En un escalar, la unidad exterior es el propio escalar, así que `Size_t`
representa su tamaño completo. En un puntero, representa el tamaño del
puntero del target. Para un `chain` estático, su almacenamiento está compuesto
por caracteres de un byte e incluye el `NUL` final. `Size_t` no puede
asociarse a `buffer`, porque siempre sería el valor redundante `1`.

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

### Contrato opcional `unique`

El comportamiento por defecto conserva el aliasing: una función con dos
parámetros de array ordinarios puede recibir dos veces el mismo array. Para
pedir una región exclusiva, el parámetro se declara como `unique` y añade el
metadato inmutable `Region_t` después de `Len_t` y `Size_t`:

```bg
func transform(
    input: unique int32[],
    input_len: Len_t,
    input_size: Size_t,
    input_region: Region_t
) void:
    return
```

La llamada sigue usando solo `transform(values)`. El compilador prueba la
procedencia del almacenamiento y rechaza aliasing potencial o procedencia
desconocida. Un parámetro `unique` puede reenviarse a otra función `unique` y
conserva su región. La prueba no separa subrangos por aritmética: si no puede
probar que son distintos, conserva el rechazo seguro.


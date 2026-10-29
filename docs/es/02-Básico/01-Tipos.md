# Intrinsecos

Catálogo de **Intrínsecos Estrictos** del lenguaje Bagron. Solo se incluyen
tipos cuyo ancho está fijado explícitamente.

| Familia | Tipo | Ancho | Descripción |
|:---|:---|---:|:---|
| Entero con signo | `int8` | 8 bits | `-128` a `127`; entero compacto con signo. |
| Entero con signo | `int16` | 16 bits | `-32 768` a `32 767`; entero con signo de rango corto. |
| Entero con signo | `int32` | 32 bits | `-2 147 483 648` a `2 147 483 647`; entero general con signo. |
| Entero con signo | `int64` | 64 bits | `-9 223 372 036 854 775 808` a `9 223 372 036 854 775 807`; entero amplio con signo. |
| Entero sin signo | `uint` | 32 bits | `0` a `4 294 967 295`; entero sin signo de 32 bits. |
| Entero sin signo | `uint8` | 8 bits | `0` a `255`; entero compacto sin signo. |
| Entero sin signo | `uint16` | 16 bits | `0` a `65 535`; entero sin signo de rango corto. |
| Entero sin signo | `uint32` | 32 bits | `0` a `4 294 967 295`; entero general sin signo. |
| Entero sin signo | `uint64` | 64 bits | `0` a `18 446 744 073 709 551 615`; entero amplio sin signo. |
| Datos crudos | `byte` | 8 bits | `0` a `255`; unidad de datos crudos, no entero numérico. |
| Punto flotante | `middle` | 16 bits | `±65 504` finitos; flotante binario de precisión media. |
| Punto flotante | `float` | 32 bits | `±3.402823466 × 10^38` finitos; flotante de precisión simple. |
| Punto flotante | `double` | 64 bits | `±1.7976931348623157 × 10^308` finitos; flotante de precisión doble. |
| Carácteres | `char` | 8 bits | `0` a `127` en ASCII; representa un carácter. |
| Lógico | `bool` | 1 bit lógico | `false` o `true`; almacenamiento y alineación mínimos de 1 byte. |
| Ausencia de valor | `void` | 0 bits | Sin rango; indica que no existe un valor. |

## Diferencia entre `char` y `byte`

Aunque ambos ocupan 8 bits, representan conceptos distintos y pertenecen a
familias semánticas separadas:

| Tipo | Rango | Uso principal |
|:---|:---:|:---|
| `char` | `0` a `127` | Un carácter ASCII o un buffer de texto. |
| `byte` | `0` a `255` | Un octeto de datos binarios sin interpretación textual. |

`char` se utiliza para texto. Sus arrays pueden inicializarse con literales de
cadena ASCII y conservan la disciplina del terminador `NUL` cuando representan
buffers de caracteres.

`byte` se utiliza para datos crudos: archivos, buffers binarios, bytes de red o
valores que no deben interpretarse como texto. Un array de `byte` puede contener
cualquier valor entre `0` y `255`, incluido `0`, sin que ese valor tenga un
significado especial de terminación.

No existe conversión implícita entre `char`, `byte` y `uint8`. El mismo ancho de
almacenamiento no elimina la diferencia semántica ni permite escalar `byte`
como si fuera un entero numérico.

## ¿Por qué `int` no está soportado?

`int` no está soportado porque su ancho puede cambiar según el target y hacer
que el mismo código tenga rangos, conversiones y representaciones diferentes.
Bagron exige que cada entero tenga un ancho explícito y trazable: usa `int8`,
`int16`, `int32` o `int64` según el rango requerido.

## Formas y reglas de conversión

Bagron aplica conversiones implícitas únicamente cuando el cambio es seguro y
trazable. La regla general es:

1. El origen y el destino deben pertenecer a la misma familia.
2. Deben conservar el mismo signo.
3. El destino debe tener un ancho estrictamente mayor.
4. El valor debe conservarse sin truncamiento ni reinterpretación.

El mismo tipo siempre es válido, pero no constituye una conversión. Dos tipos
con el mismo ancho tampoco se convierten automáticamente si tienen nombres
distintos: `byte` y `uint8`, o `uint` y `uint32`, siguen siendo tipos distintos.

### Enteros con signo

Los enteros con signo se pueden ensanchar en esta dirección:

```text
int8  -> int16 -> int32 -> int64
```

Por ejemplo:

```bg
small: int8 = 100
wide: int16 = small       ; válido: 8 bits -> 16 bits
larger: int32 = wide      ; válido: 16 bits -> 32 bits
```

El estrechamiento está prohibido:

```bg
wide: int16 = 100
small: int8 = wide        ; error: 16 bits -> 8 bits
```

### Enteros sin signo

Los enteros numéricos sin signo siguen la misma regla. `uint` es un tipo
distinto de 32 bits:

```text
uint8 -> uint16 -> uint32 -> uint64
```

Además, `uint8`, `uint16`, `uint32` y `uint` pueden escalar a `uint64` cuando
su ancho de origen es menor. `uint` no se intercambia automáticamente con
`uint32`, porque ambos tienen 32 bits pero no son el mismo tipo. `byte` queda
fuera de esta cadena: es un tipo de datos crudos y no se escala.

```bg
octet: byte = 255
word: uint16 = octet       ; error: byte no se escala
number: uint8 = 255
count: uint64 = number      ; válido: 8 bits -> 64 bits
same_width: uint32 = count ; error: 64 bits -> 32 bits
```

`byte` y `uint8` no se convierten entre sí: tienen el mismo ancho, pero
representan conceptos diferentes. Un `byte` solo puede permanecer como
`byte`; los cálculos numéricos deben usar un tipo entero sin signo. Aunque su
representación tenga 8 bits y sus valores sean no signados, `byte` no pertenece
a la familia `uint`.

### Punto flotante

Los tipos flotantes pertenecen a una familia separada y solo pueden escalarse
entre sí, siguiendo esta dirección:

```text
middle -> float -> double
```

No se permite convertir automáticamente un entero a un flotante, un flotante
a un entero, ni un flotante de mayor ancho a uno menor.

### Literales de compilación

Un literal entero es un valor conocido durante la compilación. Puede inicializar
un tipo entero más pequeño si su valor cabe exactamente en el rango del destino;
esto no es una conversión de un valor almacenado ni una reducción en runtime:

```bg
small: int8 = 127       ; válido: el literal cabe en -128..127
octet: uint8 = 255      ; válido: el literal cabe en 0..255
bad: int8 = 128         ; error: queda fuera del rango de int8
negative: uint8 = -1    ; error: queda fuera del rango sin signo
```

### Dónde se aplican las reglas

Las mismas reglas se aplican en:

- inicializaciones y asignaciones;
- argumentos de funciones;
- valores de retorno;
- operandos de operaciones aritméticas, comparaciones y operaciones bitwise.

Cuando una operación combina enteros de la misma familia, Bagron usa el
operando de mayor ancho como tipo común. Si los signos son distintos o no hay
un ensanchamiento seguro, la expresión se rechaza en compilación:

```bg
a: int8 = 1
b: int16 = 2
c: int16 = a + b       ; válido: el resultado usa int16

u: uint8 = 1
s: int16 = 2
bad: int16 = u + s      ; error: mezcla con y sin signo
```

Bagron no ofrece un casteo general para saltarse estas restricciones. Las
conversiones entre familias, los cambios de signo y los estrechamientos deben
rechazarse explícitamente por el compilador.

## Datos especiales

### `usize` e `isize`

`usize` e `isize` son los tipos destinados a representar tamaños, índices,
capacidades y distancias relacionadas con memoria. Su ancho cambia con el
target: normalmente son de 32 bits en targets de 32 bits y de 64 bits en
targets de 64 bits.

Como regla práctica, todo valor cuyo tamaño deba seguir la arquitectura debería
declararse con estas palabras:

- `usize` para cantidades de tamaño no negativo;
- `isize` cuando la cantidad pueda necesitar signo.

No forman parte del catálogo de Intrínsecos Estrictos porque su ancho no es
fijo. Los tipos estrictos deben reservarse para datos cuyo tamaño exacto sea
parte del contrato.

### Metatipos `Len_t` y `Size_t`

`Len_t` y `Size_t` no son valores que el usuario escriba en una llamada. Son
metatipos expansivos que aparecen en firmas de funciones y cuyo argumento se
genera automáticamente durante la compilación. Internamente usan el ancho de
`usize` del target.

`Len_t` representa la longitud exacta del dato asociado. Solo funciona con
arrays y con el caso especial de `chain`, que es estático, inmutable y seguro:

- en un array, usa la cantidad declarada de elementos;
- en un `chain` estático, incluye el terminador `NUL`;
- conserva los elementos reservados aunque el texto inicial sea más corto.

```bg
name: char[16] = "Hola"

func foo(data: char[], length: Len_t, size: Size_t) void:
    return

foo(name)                 ; Bagron expande Len_t a 16 y Size_t a 1
```

`Size_t` representa el tamaño en bytes del tipo asociado:

- en un array, usa el tamaño en bytes de un solo elemento;
- en un escalar, usa el tamaño en bytes del tipo;
- en un puntero, usa el tamaño del puntero del target.

Para obtener el tamaño total de un array se multiplican ambos metadatos:

```text
tamaño total = Len_t * Size_t
```

Por ejemplo, `int32[3]` produce `Len_t = 3` y `Size_t = 4`, por lo que ocupa
`12` bytes. `char[5]` produce `Len_t = 5` y `Size_t = 1`, por lo que ocupa
`5` bytes. `Size_t` no representa una longitud de elementos y no tiene por
qué ser múltiplo de dos.

```bg
values: int32[3] = {1, 2, 3}

func send(data: int32[], length: Len_t, bytes: Size_t) void:
    return

send(values)              ; Bagron expande Len_t a 3 y Size_t a 4
```

Los metatipos siempre se expanden hacia la derecha del parámetro visible al
que están asociados. Para cada array, `Len_t` y `Size_t` son obligatorios y
deben aparecer como un bloque consecutivo en ese orden. Se pueden pedir
metadatos para varios parámetros mientras cada bloque conserve ese orden:

```bg
values: int32[3] = {1, 2, 3}
other: int32[3] = {4, 5, 6}

func send(
    data: int32[],
    length: Len_t,
    bytes: Size_t,
    other_data: int32[],
    other_length: Len_t,
    other_bytes: Size_t
) void:
    return

send(values, other)       ; expansión interna: send(values, 3, 4, other, 3, 4)
```

El llamador solo proporciona los argumentos visibles. No puede insertar,
reemplazar ni calcular manualmente los argumentos `Len_t` o `Size_t`.

En cualquier firma que reciba un array, `Len_t` y `Size_t` son obligatorios y
deben aparecer consecutivamente en ese orden, incluso si la función es
`@unsafe`. `T[]` en una firma no declara almacenamiento dinámico: representa
un array estático recibido con metadatos que pueden reenviarse. `chain` es la
excepción y conserva su firma especial con `Len_t`.

## `Bint<n>` y `uBint<n>`

`Bint<n>` y `uBint<n>` son tipos de ancho bit a bit:

- `Bint<n>` representa un campo con signo de exactamente `n` bits;
- `uBint<n>` representa un campo sin signo de exactamente `n` bits.

`Bint<n>` requiere un mínimo de 2 bits, porque un entero con signo de 1 bit
solo tendría el rango `-1..0`. `uBint<n>` puede usar desde 1 bit y con
`uBint<1>` su rango es `0..1`.

No son tipos de almacenamiento libre. Bagron solo los permite como campos de
`flags`, donde el compilador controla el tipo base, el empaquetado, el orden y
el desplazamiento de cada campo. No tienen dirección independiente ni deben
usarse como variables, parámetros, retornos, arrays o punteros.

### `bool` dentro de `flags`

`bool` se permite como campo de `flags` con un ancho lógico de exactamente
1 bit. Comparte el almacenamiento empaquetado del tipo base de `flags`, sin
convertirse en un entero ni permitir conversiones hacia `byte` o `uint8`.
Su almacenamiento físico mínimo sigue siendo de 1 byte y no puede tomarse su
dirección de forma independiente.

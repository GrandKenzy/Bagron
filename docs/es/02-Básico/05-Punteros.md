# Punteros

Un puntero es un valor que contiene la dirección de un dato y conserva el tipo
del objeto al que apunta. En Bagron, una dirección no se trata como un entero
ordinario: su nivel de indirección, su tipo apuntado, su constancia y su
procedencia forman parte de las reglas del compilador.

Los punteros permiten trabajar con memoria mapeada, estructuras compartidas,
APIs externas y funciones que modifican datos del llamador. También introducen
riesgos que no existen al usar valores por copia, por lo que Bagron exige una
sintaxis explícita y separa las operaciones demostrables de la frontera
`@unsafe`.

## Declaración

El asterisco se escribe en el declarador, antes de los dos puntos:

```bg
value: int32 = 10
pointer *: int32 = $value
```

`pointer` tiene tipo `int32*`: contiene una dirección que debe apuntar a un
`int32`. El tipo apuntado no se infiere de una conversión posterior ni puede
cambiarse arbitrariamente.

Cada asterisco representa un nivel de indirección adicional:

```bg
value: int32 = 10
pointer *: int32 = $value
pointer_pointer **: int32 = $pointer
```

En este ejemplo:

- `value` es un `int32`;
- `pointer` apunta a un `int32`;
- `pointer_pointer` apunta a un puntero que apunta a un `int32`.

Los punteros pueden aparecer como parametros de funciones:

```bg
@unsafe
func read(pointer *: int32) int32:
    return (pointer)
```

Las funciones de Bagron no retornan punteros: solo retornan intrínsecos puros o
valores agregados (`struct`, `mold`, `flags` y clases). Un puntero no es un
array y un array no se convierte implícitamente en un puntero ordinario. El
paso de arrays a funciones tiene una ABI especial descrita en [Arrays](04-Arrays.md).

## Obtener una dirección con `$`

`$` es el operador explícito de dirección. Solo puede aplicarse a un valor que
represente almacenamiento direccionable:

```bg
value: int32 = 10
pointer *: int32 = $value

struct Point:
    x: int32
    y: int32

point: Point
field *: int32 = $point.x

values: int32[3] = {1, 2, 3}
element *: int32 = $values[1]
```

El resultado conserva el tipo del dato direccionado. Si `value` es `int32`,
`$value` es `int32*`; si `values[1]` es `int32`, `$values[1]` también es
`int32*`.

### Qué puede direccionarse

Se puede obtener la dirección de:

- una variable local o global;
- un campo direccionable de un `struct` o `mold`;
- un elemento de un array con `$array[indice]`;
- una variable que ya sea un puntero, produciendo un nivel adicional.

En el caso especial de `chain`, `$texto[indice]` sí puede obtener la dirección
de un carácter concreto, pero el resultado conserva la constancia del rodata y
solo es compatible con `const char*`.

No se puede aplicar `$` a:

- literales, expresiones temporales o resultados no direccionables;
- el array completo (`$values`); debe seleccionarse un elemento;
- un campo individual de `flags`, porque un bitfield no tiene dirección propia;
- un `chain`, que es almacenamiento estático e inmutable;
- `Null`.

```bg
values: int32[3] = {1, 2, 3}
; bad *: int32 = $values       ; inválido: el array completo no es un elemento
```

La dirección de un puntero es la dirección de su variable, no la dirección del
objeto al que apunta:

```bg
value: int32 = 10
pointer *: int32 = $value
pointer_slot **: int32 = $pointer
```

`$pointer` apunta al almacenamiento de `pointer`; no equivale a `pointer`.

## Desreferenciación

La desreferenciación se escribe mediante paréntesis. Una pareja de paréntesis
consume un nivel de puntero:

```bg
value: int32 = 10
pointer *: int32 = $value

copy: int32 = (pointer)
(pointer) = 20
```

La expresión `(pointer)` es un `int32` lvalue: puede leerse y, si el dato no
es constante, también escribirse. Los niveles múltiples se desreferencian de
uno en uno:

```bg
value: int32 = 10
pointer *: int32 = $value
pointer_pointer **: int32 = $pointer

((pointer_pointer)) = 30
```

El asterisco de la declaración no es un operador de desreferenciación. Bagron
no usa la forma ambigua `*pointer` para leer memoria; la declaración y el
acceso tienen sintaxis separadas.

Desreferenciar un valor que no es puntero es un error. Desreferenciar `void*`
también es un error, porque `void` no describe el tipo del objeto apuntado:

```bg
handle *: void = Null
; value: int32 = (handle) ; inválido: void* no tiene tipo apuntado
```

Un `void*` puede almacenarse y pasarse a una API externa o recibirse como un
puntero tipado mediante una firma compatible, pero no puede leerse directamente
ni retornarse desde una función de Bagron.

## `Null`

`Null` es el literal de puntero nulo. Puede inicializar cualquier puntero de
datos:

```bg
pointer *: int32 = Null
handle *: void = Null
```

`Null` no es un tipo de almacenamiento ordinario, no es un entero cero y no
puede desreferenciarse. El backend inserta una comprobación antes de cada
desreferenciación; si la dirección es nula, la ejecución termina mediante una
trampa en lugar de leer o escribir memoria nula.

`@unsafe` no convierte `Null` en una dirección válida. La frontera insegura
permite trabajar con procedencias que el compilador no puede demostrar, pero
no elimina la protección contra una desreferenciación nula.

## Constancia de punteros

La constancia del puntero y la constancia del objeto apuntado son propiedades
independientes:

```bg
const destination *: int32 = Null
readonly_value *: const int32 = Null
const readonly_destination *: const int32 = Null
```

| Declaración | Puede cambiar la dirección guardada | Puede modificar el objeto apuntado |
|:---|:---:|:---:|
| `destination *: int32` | Sí | Sí |
| `const destination *: int32` | No | Sí |
| `readonly_value *: const int32` | Sí | No |
| `const readonly_destination *: const int32` | No | No |

Ejemplo:

```bg
first: int32 = 10
second: int32 = 20

const_destination *: int32 = $first
; const_destination = $second ; error: el puntero es constante

readonly *: const int32 = $first
; (readonly) = 30              ; error: el valor apuntado es constante
```

Un puntero a un dato mutable puede entregarse a un parámetro que solo lea ese
dato (`*: const T`). La conversión inversa, de un puntero a dato constante a un
puntero que permita escritura, se rechaza. No se permite eliminar `const` de
forma implícita.

`volatile` es otra propiedad distinta. Cuando el destino es un agregado
`volatile`, las lecturas y escrituras a través de un puntero a ese agregado se
conservan como accesos volátiles. `volatile` no hace que el puntero sea
constante ni que el objeto sea inmutable.

## Procedencia y frontera segura

El compilador conserva la procedencia conocida de las direcciones. Esto permite
rechazar desreferenciaciones que no puede justificar estáticamente.

| Origen del puntero | Desreferenciación en función segura |
|:---|:---:|
| `$variable` local o global | Permitida si el tipo es válido. |
| `$array[indice]` con acceso válido | Permitida si el acceso fue demostrado. |
| Parámetro `T*` recibido desde fuera | Rechazada: procedencia desconocida. |
| Puntero recibido desde una frontera externa | Rechazada: procedencia desconocida. |
| Puntero leído desde almacenamiento crudo de un `mold` | Rechazada: procedencia desconocida. |
| `Null` | Se compila, pero su desreferenciación produce una trampa. |

Una función puede recibir un puntero opaco, pero no puede retornarlo. Para leerlo
o escribirlo cuando su procedencia no puede demostrarse, la función
debe declarar explícitamente `@unsafe`:

```bg
@unsafe
func write(pointer *: int32) void:
    (pointer) = 42
    return
```

`@unsafe` no cambia el tipo del puntero ni comprueba que la dirección sea
válida. Solo reconoce que el programador asume la responsabilidad por la
procedencia, la vida del objeto y los límites del acceso.

Una función segura tampoco puede llamar a una función `@unsafe`. La frontera
debe mantenerse pequeña y visible para que el resto del programa conserve las
garantías estáticas.

## Vida útil y escape de direcciones

Un puntero no posee el objeto al que apunta. No mantiene vivo un valor ni
extiende automáticamente la vida de una variable.

Bagron no permite retornar punteros desde funciones, por lo que una dirección
no puede escapar mediante un retorno, sea local o externa:

```bg
func invalid() int32*:
    value: int32 = 10
    return $value       ; error: las funciones no retornan punteros
```

`@unsafe` no cambia esta regla; solo permite operaciones de lectura y escritura
cuya procedencia no puede demostrarse.

Los punteros pueden aliasar el mismo almacenamiento. Escribir mediante uno de
ellos cambia el valor que leerá cualquier otro puntero válido al mismo objeto:

```bg
value: int32 = 1
first *: int32 = $value
second *: int32 = $value

(first) = 7
result: int32 = (second) ; 7
```

`unique` no modifica esta regla de punteros crudos. Solo aplica a parámetros de
array y `buffer`, y requiere una `Region_t` demostrable; una dirección obtenida
de un puntero no puede proporcionar por sí sola ese contrato seguro.

## Indexación de punteros

Un puntero crudo no lleva longitud ni límites. Por eso incluso un índice
literal sobre un puntero exige `@unsafe`:

```bg
@unsafe
func read_at(pointer *: int32, index: usize) int32:
    return pointer[index]
```

El compilador no puede demostrar que `index` apunta a un objeto válido. La
indexación de un array fijo es diferente: el tipo contiene sus dimensiones y
un índice literal puede comprobarse en una función segura. Un `T[]` de una
firma conserva sus metadatos, pero un parámetro `T*` no tiene `Len_t` ni
`Size_t` asociados.

No existe aritmética implícita de punteros:

```bg
; next: int32* = pointer + 1  ; inválido
; test: bool = pointer == Null ; inválido: los punteros no son comparables
```

Para acceder a una posición de un buffer externo debe usarse la indexación de
puntero dentro de una función `@unsafe`, con los límites garantizados por el
contrato de esa función o por la ABI externa.

## Punteros a agregados y MMIO

Un puntero puede apuntar a un `struct` o a un `mold`. Primero se desreferencia
el agregado y después se accede a su campo:

```bg
struct Point:
    x: int32
    y: int32

@unsafe
func move(point *: Point) void:
    (point).x = 10
    (point).y = 20
    return
```

Para registros de hardware, el agregado debe declararse `volatile`:

```bg
volatile struct UART:
    status: uint32
    control: uint32

@unsafe
func read_status(registers *: UART) uint32:
    return (registers).status

@unsafe
func write_control(registers *: UART, value: uint32) void:
    (registers).control = value
    return
```

`volatile` conserva cada acceso, pero no hace atómicas las operaciones ni
valida que la dirección corresponda al dispositivo correcto. La dirección
base y el contrato MMIO siguen siendo responsabilidad de la integración con
el target.

Los campos de `flags` se manipulan como bits dentro de su contenedor y no
pueden convertirse en punteros independientes. Un campo de `mold` que contiene
un puntero se considera de procedencia desconocida al leerse; su
desreferenciación requiere `@unsafe`.

## Punteros y ABI externa

Los punteros ocupan el ancho del puntero del target y se pasan a la ABI como
direcciones tipadas. `void*` se representa como un puntero de bytes opaco y es
útil para handles y APIs externas:

```bg
extern windows "kernel32":
    GetStdHandle(kind: uint32) *: void

extern windows "user32":
    MessageBoxA(window *: void, text *: char, caption *: char, flags: uint32) int32

extern c "ucrt":
    printf(format *: char) int32
```

El primer identificador después de `extern` declara el dominio de la librería:
`windows` solo es válido cuando el target usa `System 'windows'`; `c` declara
una librería C del target y es válido en targets de sistema, pero ningún dominio
externo está permitido en `baremetal`. El dominio también se conserva en el
registro de enlaces (`windows:kernel32`, `windows:user32`, `c:ucrt`).

La forma antigua `extern "library":` ya no es válida después de migrar los
usos internos; la gramática la reconoce solo para emitir un diagnóstico claro.

Una firma `extern` puede usar punteros a escalares, `void` y agregados
compatibles con la ABI. No puede usar arrays, `chain`, `Null` como tipo de
firma ni metatipos `Len_t`/`Size_t`.

### Descriptores opaque

Un descriptor nativo no debe declararse como un alias de puntero o entero. La
forma `opaque` conserva un nombre nominal y deja su representación ABI bajo
control del compilador:

```bg
opaque WINDOWS_FILE_DESCRIPTOR: void*
opaque LINUX_FILE_DESCRIPTOR: int32

extern windows "kernel32":
    GetStdHandle(kind: uint32) WINDOWS_FILE_DESCRIPTOR
    CloseHandle(handle: WINDOWS_FILE_DESCRIPTOR) int32

@unsafe
func create_file() WINDOWS_FILE_DESCRIPTOR:
    return GetStdHandle(0)

func close_file(handle: WINDOWS_FILE_DESCRIPTOR) void:
    return
```

El valor Windows se emite como `ptr` LLVM y el Linux como `i32`, sin tags ni
estructuras runtime. En código fuente un descriptor opaque solo coincide con
otro descriptor del mismo nombre: no se puede desreferenciar, indexar, tomar su
dirección, convertirlo a entero o puntero, ni mezclarlo con el descriptor de
otra plataforma. El backend conserva únicamente la representación declarada.

Los retornos y las variables locales de descriptor comienzan en estado
`owned`; los parámetros son `borrowed`. Las llamadas ordinarias solo prestan el
valor durante la llamada. Las funciones `close_*` consumen un descriptor
`owned` y lo marcan `closed`, por lo que un segundo cierre se rechaza
estáticamente. Estos estados no se almacenan en runtime.

Los punteros a arrays no reciben la conversión especial de los parámetros de
array. Un `buffer` es distinto: su almacenamiento lo administra Bagron y nunca
puede cruzar directamente un `extern` como puntero derivado de `$data[0]`, ni
siquiera dentro de `@unsafe`. El tipo `buffer` sí puede cruzar funciones Bagron
mediante `buffer[]`. Las APIs como `WriteFile` pueden seguir recibiendo un
puntero crudo o la dirección explícita de un array fijo; esos casos siguen bajo
la responsabilidad de la frontera `@unsafe`.

## Restricciones resumidas

Bagron aplica estas reglas para mantener los punteros trazables:

- la declaración indica explícitamente cada nivel de puntero;
- `$` solo obtiene direcciones de almacenamiento direccionable;
- la desreferenciación usa paréntesis y consume un nivel por operación;
- `Null` solo representa una dirección nula y nunca es un objeto válido;
- `void*` es opaco y no puede desreferenciarse;
- no hay conversiones implícitas entre punteros e enteros;
- no hay aritmética ni comparación ordinaria de punteros;
- indexar un puntero crudo requiere `@unsafe`;
- los arrays no se convierten silenciosamente en punteros crudos;
- `const` del puntero y `const` del objeto apuntado se comprueban por separado;
- una función segura no puede llamar a `@unsafe`;
- una función no puede retornar punteros, arrays ni `buffer`;
- `chain` no puede declararse como puntero;
- un bitfield de `flags` no tiene dirección independiente.
- un descriptor `opaque` es nominal y conserva su estado `owned`/`borrowed`/`closed`
  solo durante el análisis estático.

`callptr` es una categoría distinta de puntero destinada a referencias a
funciones. No debe confundirse con un puntero a datos: su firma debe coincidir
con la función asociada y su emisión LLVM/ABI todavía no forma parte del
contrato de punteros de datos de esta versión.

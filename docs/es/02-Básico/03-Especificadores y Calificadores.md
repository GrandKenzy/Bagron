# Especificadores y Calificadores

Los calificadores modifican la forma en que se puede usar un tipo o un
valor. Los especificadores modifican una declaración completa, su visibilidad
o la forma en que el compilador debe tratarla.

En un lenguaje de bajo nivel esto es importante porque una declaración no solo
describe qué datos existen: también puede limitar quién los modifica, indicar
si una dirección representa hardware y definir cómo se organizan los bytes y
los bits en memoria.

- Un **calificador** impone una regla de uso, como `const`.
- Un **especificador** expresa una propiedad de una declaración, como `inline`
  o `volatile`.
- Un **decorador** añade metadatos con `@`, como `@packed` o `@unsafe`.

Estas palabras no cambian arbitrariamente el tipo de un valor. Hacen explícitas
las garantías que el compilador debe conservar.

## Calificadores de tipo

### `const`

`const` declara que el valor no puede modificarse después de su inicialización.
El compilador rechaza cualquier asignación posterior. Se escribe delante del
tipo:

```bg
limite: const int32 = 10
texto: const char[6] = "Hola"
```

En los punteros, la constancia del puntero y la del valor apuntado son
independientes:

```bg
const puntero *: int32
apuntado *: const int32
const referencia *: const int32
```

- `const dato *: int32`: el puntero no puede cambiar de destino; el valor sí.
- `dato *: const int32`: el puntero puede cambiar de destino; el valor apuntado no.
- `const referencia *: const int32`: ni el destino ni el valor apuntado pueden modificarse.

Un puntero es una variable que contiene una dirección de memoria. Por eso
estas dos formas controlan cosas distintas: una puede proteger la dirección
guardada y la otra protege los datos que existen en esa dirección. `const` no
convierte los datos en secretos ni impide que otro puntero válido los cambie;
solo establece una garantía para ese acceso.

`chain` ya es inmutable por definición y no puede declararse como `const
chain`. `Len_t` y `Size_t` también son parámetros expansivos de compilación y
no aceptan `const`.

## Especificadores de declaración

### Visibilidad

`public` y `private` controlan si una declaración puede usarse desde fuera de
su ámbito. El ámbito es la parte del programa donde un nombre es visible,
como un módulo o una clase.

| Especificador | Forma | Función |
|:---|:---|:---|
| `public` | `public struct Punto:` | Hace pública la declaración. |
| `private` | `private func auxiliar() void:` | Restringe la declaración a su ámbito. |

Pueden aplicarse a variables, funciones, `struct`, `mold`, `flags`, `enum`,
`class` y `TypeAlias`.

Si no se escribe ninguno, la declaración es pública por defecto.

### `inline`

`inline` es un especificador de funciones:

```bg
inline func sumar(a: int32, b: int32) int32:
    return a + b
```

Una llamada normal salta a otra dirección y vuelve después de ejecutar la
función. `inline` emite una sugerencia `inlinehint` para LLVM: permite que el
compilador inserte el cuerpo de una función pequeña directamente en el lugar
de la llamada cuando lo considere apropiado.

`inline` es una petición, no una obligación: el compilador puede ignorarla si
la expansión aumenta demasiado el código o no es conveniente. No cambia la
firma, el tipo de retorno ni las reglas de seguridad de la función.

## Especificadores de almacenamiento

### `volatile`

El compilador normalmente puede reutilizar una lectura, eliminar una escritura
que parezca innecesaria o reorganizar accesos ordinarios. `volatile` le indica
que cada lectura y cada escritura del agregado representa una interacción real
con memoria externa y debe conservarse.

`volatile` se aplica a agregados completos:

```bg
volatile struct Registro:
    estado: uint32

volatile mold Vista:
    valor: uint32

volatile flags Estado uint8:
    activo: bool = false
    reservado: uBint<7> = 0
```

Los accesos de lectura y escritura al almacenamiento del agregado se
conservan como operaciones volátiles. Esto es útil para memoria mapeada,
registros de hardware o memoria compartida. Un patrón típico para un bloque
MMIO usa un puntero a un agregado volátil y exige desreferenciarlo
explícitamente:

```bg
volatile struct UART:
    status: uint32
    control: uint32

@unsafe
func leer_status(registros *: UART) uint32:
    return (registros).status
```

`volatile` no hace una operación atómica ni reemplaza mutexes, barreras o un
protocolo de sincronización. Solo garantiza que el acceso de memoria no se
elimine ni se trate como una lectura o escritura ordinaria.

## Decoradores de funciones

Las funciones solo admiten decoradores de nombre simple, sin argumentos, y no
se pueden repetir. Un decorador desconocido produce un error de compilación.

| Decorador | Forma | Función |
|:---|:---|:---|
| `unsafe` | `@unsafe` | Permite operaciones que cruzan la frontera insegura, como indexación dinámica o acceso a punteros crudos. |
| `assembler` | `@assembler` | Declara una función con cuerpo de ensamblador preparado mediante `#prep assembler`. También implica `unsafe`. |

Una función segura no puede llamar a una función `@unsafe` o `@assembler`.
`@unsafe` debe reservarse para la pequeña frontera que realmente necesita
operaciones sin garantía automática; el resto del programa puede permanecer
en contexto seguro. Una función `@assembler` puede tener un único bloque
`#prep` y debe terminarlo con `return asm`; también puede existir sin bloque
`#prep`, en cuyo caso solo admite un `return` normal.

## Decoradores de agregados

Estos decoradores se aplican a `struct`, `mold` y `flags` según la tabla de
compatibilidad de [Estructuras](02-Estructuras.md).

| Decorador | Forma | Función |
|:---|:---|:---|
| `packed` | `@packed` | Reduce o elimina el padding automático del layout. |
| `align` | `@align(N)` | Solicita una alineación explícita; `N` debe ser una potencia de dos entre 1 y 64. |
| `order_lsb` | `@order_lsb` | En `flags`, asigna los campos desde los bits menos significativos. |
| `order_msb` | `@order_msb` | En `flags`, asigna los campos desde los bits más significativos. |

`@order_lsb` y `@order_msb` son alternativas del orden de bits y no deben
usarse simultáneamente.

### Cuándo usar cada decorador

#### `@packed`

El compilador suele insertar padding para que cada campo respete la alineación
natural de su tipo. `@packed` reduce ese espacio y hace que el layout sea más
compacto y predecible. Es útil al describir formatos binarios, registros de
hardware o estructuras compatibles con una ABI externa.

El coste es que algunos campos pueden quedar desalineados. Debe usarse solo
cuando el layout compacto sea parte del contrato; no es una optimización
general para cualquier estructura.

#### `@align(N)`

Solicita que el agregado comience con una alineación concreta. `N` debe ser una
potencia de dos entre `1` y `64`:

```bg
@align(8)
struct Bloque:
    valor: int64
```

Sirve para cumplir contratos de hardware, ABI o instrucciones que requieren
direcciones alineadas. No cambia el orden de los campos ni convierte un tipo
en otro.

#### `@order_lsb` y `@order_msb`

Estos decoradores solo determinan desde qué extremo del contenedor se asignan
los campos de `flags`. No son una conversión de endianess y no cambian por sí
solos el orden de bytes de un entero.

## Verificación de `volatile`

El compilador cuenta con pruebas automatizadas para confirmar que `volatile`
se conserva en lecturas y escrituras de `struct`, `mold` y `flags`, incluidos
los bitfields de un bit. También se prueba el acceso directo, el acceso a
registros MMIO mediante punteros con desreferenciación explícita y la
diferencia frente a agregados no volátiles.

Estas pruebas verifican el LLVM generado: los accesos volátiles se emiten como
operaciones `load volatile` y `store volatile`, mientras que los agregados
normales conservan operaciones de memoria ordinarias.

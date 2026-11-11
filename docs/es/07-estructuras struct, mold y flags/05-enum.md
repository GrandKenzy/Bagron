# 05. `enum`

`enum` declara un tipo nominal respaldado por un entero escalar. Cada miembro
se guarda como metadata del tipo junto con su valor; no se genera una tabla
runtime, una etiqueta adicional ni una representación distinta de la base.

## Declaración y base

```bg
enum Nombre [TipoBase]:
    MIEMBRO,
    OTRO = literal_entero
```

Puede llevar `public` o `private`; si se omite, es pública. La base es
`int32` por defecto. Las bases aceptadas son `int8`, `int16`, `int32`, `int64`,
`uint8`, `uint16`, `uint32`, `uint64`, `byte`, `isize` y `usize`.

La base debe ser un entero escalar sin `const`. `byte` sí es válido como entero
sin signo de 8 bits. No puede ser `bool`, `Bint<n>`, `uBint<n>`, un puntero, un
array, `buffer` ni un metatipo
(`Len_t`, `Size_t`, `Signed_t` o `Region_t`).

## Secuencia de valores

El primer valor implícito es `0`; cada miembro siguiente continúa desde el
último valor más uno. Un valor explícito reinicia la secuencia:

```bg
enum Resultado int16:
    DESCONOCIDO,       ; 0
    ACEPTADO = 200,    ; 200
    REINTENTO,         ; 201
    RECHAZADO = -1,    ; -1
    CANCELADO          ; 0
```

El valor explícito debe ser un literal entero, no una expresión ni un nombre.
El incremento no busca el siguiente número libre: los valores pueden
repetirse. Los nombres no pueden repetirse. La coma entre miembros es
obligatoria y la coma final opcional.

Todos los valores, incluidos los implícitos, deben caber en el rango de la
base. Por ejemplo, `int8` acepta `-128..127` y `uint8` acepta `0..255`.

## Uso como tipo

El nombre del enum puede aparecer en variables, firmas y campos:

```bg
enum Estado uint8:
    INACTIVO,
    ACTIVO = 4

func guardar(estado: Estado) void:
    return

struct Sesion:
    estado: Estado
```

`Estado` y `uint8` son tipos nominalmente distintos. No hay conversión
implícita entre ellos, aunque compartan ancho, y la forma `as` disponible en
Bagron no es un casteo general: actualmente solo permite `byte <-> uint8`.

Los miembros son constantes de expresión tipadas:

```bg
estado: Estado = Estado.ACTIVO
es_activo: bool = estado == Estado.ACTIVO
```

El resultado de `Estado.ACTIVO` tiene el tipo nominal `Estado`, es literal y
conserva el valor entero asociado durante la compilación. No publica una
variable, no reserva memoria ni crea un selector runtime. Puede usarse en
inicializaciones, argumentos, retornos y comparaciones con valores del mismo
enum. No se convierte automáticamente a `uint8` ni a otro entero, y dos enums
distintos no son compatibles aunque tengan la misma base.

## Layout y ABI

Un enum no es un agregado. LLVM lo baja directamente al escalar de su base:

```text
enum Estado uint8    -> i8
enum Resultado int32 -> i32
```

No hay tag runtime, tabla de miembros ni padding adicional. Dentro de un
`struct` o `mold`, el campo ocupa la representación ABI de la base, mientras
el frontend conserva la identidad nominal para comprobar tipos y asignaciones.

## Relación con `struct`, `mold` y `flags`

| Tipo | Representa | Campos | Almacenamiento |
|:---|:---|:---:|:---:|
| `enum` | Nombres asociados a enteros | Miembros declarativos | Su base escalar |
| `struct` | Campos independientes | Sí | Separado por campo |
| `mold` | Vistas de una región | Sí | Superpuesto |
| `flags` | Bits combinables | Bitfields | Dentro de su base |

Usa `enum` para estados o códigos individuales. Usa `flags` cuando varios bits
puedan estar activos simultáneamente:

```bg
flags Permisos uint8:
    leer: uBint<1> = 0
    escribir: uBint<1> = 0
    reservado: uBint<6> = 0
```

`enum` no admite campos de bits, `@order_msb`, `@packed` ni `@align`; esos
conceptos pertenecen a `flags` o a los agregados con layout. `volatile` tampoco
convierte un enum en agregado: si hace falta volatilidad, califica el agregado
que lo contiene.

## Diagnósticos habituales

- `El tipo base de un enum debe ser un entero escalar sin constancia`: base no
  permitida, puntero, array o `const`.
- `El miembro ... ya fue declarado`: nombre de miembro repetido.
- `El valor ... esta fuera del rango`: valor explícito o implícito fuera de la
  base.
- `El tipo ... no existe` al usarlo en un campo o firma: enum no visible,
  import ausente o declaración privada.

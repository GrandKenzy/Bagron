# Intrínsecos

Bagron ofrece enteros de ancho explícito (`int8`…`int64` y sus variantes
`uint`), `byte`, `char`, `bool`, `middle`, `float`, `double`, `usize`, `isize`,
`void` y `Never`. Los tipos definidos mediante `#defint` y `#defuint` siguen
las capacidades de enteros que soporte LLVM.

## Tipos no escalares

| Categoría | Forma | Contrato |
|:---|:---|:---|
| Array | `T[N]`, hasta tres dimensiones | Almacenamiento contiguo y forma fija. |
| Array abierto | `T[]` | Vista de un array fijo recibida por una función. |
| Buffer | `buffer[N]` o `buffer[]` | Descriptor de bytes con ownership estático. |
| Puntero | `T*` | Dirección tipada; su uso fuera de procedencia conocida requiere `@unsafe`. |
| Texto | `chain` | Bytes UTF-8 constantes terminados en `NUL`. |
| Tipo nominal | `enum`, `struct`, `mold`, `fields`, `class` | Layout y compatibilidad definidos por su declaración. |
| Descriptor opaco | `opaque Nombre: tipo` | Handle nominal con ownership comprobable. |

`Null` es un literal de puntero nulo, no un tipo almacenable. `Never` solo
puede ser retorno de una función que no regresa.

## `char`, `byte` y texto

`char` y `byte` ocupan un byte, pero `char` expresa texto y `byte` datos crudos.
Un literal `chain` puede copiarse explícitamente a `char[]`; la copia contiene
los bytes UTF-8 y su `NUL`.

```bg
message: chain = "Hola"
copy: char[] = message
raw: byte[4] = {0, 1, 2, 255}
```

## Miembros derivados

La metadata ya no se declara como parámetros. Se consulta con miembros del
compilador:

```bg
func inspect(data: int32[]) usize:
    return data.<len> * data.<size>
```

`.<len>` es la primera dimensión del array, la longitud del descriptor de un
`buffer` o los bytes de un `chain` incluyendo el `NUL`. `.<size>` es el tamaño
ABI del escalar o de un elemento exterior del array. `.<region>` es una
consulta simbólica de procedencia `unique`; no es un valor runtime.

Los tres miembros son de solo lectura. `Len_t`, `Size_t`, `Signed_t` y
`Region_t` fueron retirados y producen diagnóstico si aparecen en una firma.

## `fields`, `Bint` y enteros definidos

`Bint(n)` es un limb crudo de ancho fijo y solo puede aparecer dentro de un
`fields`:

```bg
@signed
fields int128:
    lo: Bint(64)
    hi: Bint(64)
```

Los enteros nominales se definen en el nivel de módulo:

```bg
#defint 128, int128
#defuint 128, uint128
```

El nombre definido puede usarse como cualquier tipo entero compatible. Su
signedness pertenece al tipo y no requiere metadata adicional.

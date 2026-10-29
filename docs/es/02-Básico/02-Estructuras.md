# Estructuras

| Tipo | Firma | Qué es |
|:---|:---|:---|
| `struct` | `struct Nombre:` | Agrupación nominal de campos con almacenamiento independiente. |
| `mold` | `mold Nombre:` | Vista nominal de almacenamiento superpuesto, similar a una unión. |
| `flags` | `flags Nombre TipoBase:` | Conjunto nominal de campos empaquetados por bits sobre un tipo base entero sin signo. |

Los campos se declaran con la forma `nombre: Tipo`.

## `struct`

Un `struct` agrupa varios campos bajo un nombre único. Cada campo conserva su
propio tipo y almacenamiento, y el conjunto se trata como un solo valor.

### Firma

```bg
struct Nombre:
    campo: Tipo
    otro: OtroTipo
```

### Decoradores y especificadores compatibles

| Elemento | Forma | Función |
|:---|:---|:---|
| `packed` | `@packed` | Elimina el padding automático entre campos. |
| `volatile` | `volatile struct Nombre:` | Conserva los accesos al almacenamiento como operaciones volátiles. |
| `align` | `@align(N)` | Solicita una alineación explícita para el tipo. |

`@align(N)` recibe el valor de alineación solicitado para el `struct`.

## `mold`

Un `mold` define varias vistas nominales sobre un mismo bloque de
almacenamiento. Sus campos se superponen: leer o escribir un campo puede
interpretar los mismos bytes con otro tipo.

### Firma

```bg
mold Nombre:
    campo: Tipo
    otra_vista: OtroTipo
```

### Decoradores y especificadores compatibles

| Elemento | Forma | Función |
|:---|:---|:---|
| `packed` | `@packed` | Reduce el padding del almacenamiento superpuesto. |
| `align` | `@align(N)` | Solicita una alineación explícita para el tipo. |
| `volatile` | `volatile mold Nombre:` | Conserva los accesos al almacenamiento como operaciones volátiles. |

`mold` es apropiado cuando varias representaciones deben ocupar exactamente
la misma región de memoria; no crea almacenamiento independiente para cada
campo.

## `flags`

Un `flags` empaqueta campos lógicos dentro de un tipo entero base explícito.
Cada campo ocupa únicamente el número de bits que declara, por lo que resulta
adecuado para estados, permisos y otras combinaciones compactas.

### Firma

```bg
flags Nombre TipoBase:
    campo: uBint<1> = 0
    estado: Bint<3> = 0
    activo: bool = false
```

El tipo base debe ser un entero estricto sin signo: `uint8`, `uint16`,
`uint32` o `uint64`. Los campos solo pueden ser `Bint`, `uBint` o `bool`.
`Bint` requiere al menos 2 bits; `uBint` puede ocupar desde 1 bit y `bool`
ocupa 1 bit lógico. Los tipos base con signo no se aceptan porque el
contenedor solo representa bits y no necesita interpretación signed.

La suma de los anchos de todos los campos debe coincidir exactamente con el
ancho del tipo base. Si faltan bits o se excede el ancho disponible, el
compilador rechaza el `flags`; los bits reservados deben declararse de forma
explícita, por ejemplo con un campo `uBint<N>` inicializado en cero.

### Decoradores y especificadores compatibles

| Elemento | Forma | Función |
|:---|:---|:---|
| `packed` | `@packed` | Mantiene el almacenamiento del conjunto sin padding adicional. |
| `align` | `@align(N)` | Solicita una alineación explícita para el contenedor. |
| `order_lsb` | `@order_lsb` | Asigna los campos comenzando por los bits menos significativos. |
| `order_msb` | `@order_msb` | Asigna los campos comenzando por los bits más significativos. |
| `volatile` | `volatile flags Nombre TipoBase:` | Conserva los accesos al contenedor como operaciones volátiles. |

`@order_lsb` y `@order_msb` seleccionan órdenes alternativos y no deben
declararse juntos.

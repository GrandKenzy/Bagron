# `struct`, `mold`, `fields` y `enum`

## Índice

- [01. `struct` y layout](01-struct-y-layout.md)
- [02. `mold` y reinterpretación](02-mold-y-reinterpretacion.md)
- [03. `fields` y limbs](03-flags-y-bitfields.md)
- [04. Atributos de layout y `volatile`](04-layout-y-volatile.md)
- [05. `enum`](05-enum.md)

`struct`, `mold` y `fields` son agregados nominales con layouts distintos.
`enum` también es nominal, pero se baja directamente a un entero escalar y no
es un agregado.

## `struct`

```bg
struct Header:
    version: uint16
    length: uint32
```

Los campos conservan almacenamiento separado y pueden direccionarse con
`$header.version`. `@packed` reduce padding y `@align(N)` solicita alineación.

## `mold`

```bg
mold WordView:
    whole: uint32
    bytes: byte[4]
```

Los campos comparten la misma región. Leer un campo después de escribir otro
reinterpreta los bytes, no convierte el tipo. Un puntero leído de un `mold`
tiene procedencia desconocida y su desreferenciación requiere `@unsafe`.

## `fields`

```bg
fields Permissions:
    read: Bint(1)
    write: Bint(1)
    reserved: Bint(6)
```

Cada campo es un limb crudo independiente de `n` bits y puede direccionarse
como un campo normal. No hay contenedor implícito ni aritmética automática del
agregado. Los literales son posicionales y deben tener la aridad exacta:

```bg
bits: Permissions = {1, 0, 63}
```

`@signed` agrega un único bit oculto de signo al final del layout completo,
sin ampliar los limbs ni hacerlo accesible desde el código fuente:

~~~bg
@signed
fields int128:
    lo: Bint(64)
    hi: Bint(64)
~~~

`volatile` conserva lecturas y escrituras del agregado, útil para registros de
hardware, pero no vuelve atómicas las operaciones.

## `enum`

Un `enum` asocia nombres con valores enteros comprobados en compilación. Usa
`int32` por defecto o una base entera escalar explícita, y puede aparecer como
campo de un `struct` o `mold`:

```bg
enum Kind uint8:
    empty,
    data = 4

struct Header:
    kind: Kind
```

Los valores automáticos comienzan en `0` y continúan desde el último valor
explícito. Sus miembros se pueden usar como constantes tipadas (`Kind.data`),
pero el enum no se convierte automáticamente a su entero base. Consulta la
[referencia completa de `enum`](05-enum.md) para sintaxis, rangos, visibilidad,
ABI y límites.

# `struct`, `mold` y `flags`

## Índice

- [01. `struct` y layout](01-struct-y-layout.md)
- [02. `mold` y reinterpretación](02-mold-y-reinterpretacion.md)
- [03. `flags` y bitfields](03-flags-y-bitfields.md)
- [04. Atributos de layout y `volatile`](04-layout-y-volatile.md)

Los tres son agregados nominales, pero tienen layouts distintos.

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

## `flags`

```bg
flags Permissions uint8:
    read: uBint<1> = 1
    write: uBint<1> = 0
    reserved: uBint<6> = 0
```

La suma de anchos debe coincidir exactamente con la base. Los campos pueden ser
`uBint<N>`, `Bint<N>` o `bool`; un bitfield no tiene dirección independiente.

El orden predeterminado es LSB: el primer campo empieza en el bit `0`. Para un
contrato que numera desde el extremo más significativo se usa:

```bg
@order_msb
flags NetworkBits uint8:
    version: uBint<3> = 0
    kind: uBint<5> = 0
```

`@order_lsb` no existe: era redundante con el valor predeterminado. Estos
decoradores no cambian el orden de bytes de un entero.

`volatile` conserva lecturas y escrituras del agregado, útil para registros de
hardware, pero no vuelve atómicas las operaciones.

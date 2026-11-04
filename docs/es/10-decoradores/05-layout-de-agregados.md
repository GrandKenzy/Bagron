# 05. Layout de agregados

## `@packed`

`@packed` reduce el padding de una `class`, `struct`, `mold` o `flags`:

```bg
@packed
struct Header:
    tag: byte
    length: uint32
```

Las clases usan el mismo layout de almacenamiento que un `struct`, pero
conservan sus métodos, herencia y hooks:

```bg
@packed
@align(8)
class UInt128:
    func __init__(low: uint64, high: uint64) void:
        self.low = low
        self.high = high
```

Úsalo cuando el formato externo define offsets compactos. No lo uses como
sinónimo de atomicidad o de ausencia de alineación para todos los accesos.

## `@align(N)`

`@align` solicita una alineación explícita y solo acepta una potencia de dos
entre `1` y `64`:

```bg
@align(16)
struct SIMDValue:
    value: uint64
```

No se puede repetir el decorador. La alineación solicitada no puede reducir la
alineación natural del agregado, salvo las reglas específicas de un agregado
`@packed`.

## `@order_msb`

`@order_msb` solo se aplica a `flags` y coloca el primer bitfield desde el
extremo más significativo:

```bg
@order_msb
flags NetworkBits uint8:
    version: uBint<3> = 0
    kind: uBint<5> = 0
```

El orden predeterminado es LSB. `@order_lsb` fue retirado por ser redundante y
debe producir un error. Ninguno de estos decoradores cambia el orden de bytes
de un entero en memoria.

`volatile` es un calificador separado (`volatile struct`, `volatile mold` o
`volatile flags`): conserva accesos, pero no es `@volatile` ni hace atómicas las
operaciones.

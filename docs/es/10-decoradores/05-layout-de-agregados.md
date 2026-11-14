# 05. Layout de agregados

## `@packed`

`@packed` reduce el padding de una `class`, `struct` o `mold`:

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

## `@signed` en `fields`

`@signed` solo se aplica a `fields` y añade un único bit oculto de signo al
layout completo:

```bg
@signed
fields int128:
    lo: Bint(64)
    hi: Bint(64)
```

El bit oculto no amplía cada limb y no se puede nombrar desde el código fuente.

`volatile` es un calificador separado (`volatile struct`, `volatile mold` o
`volatile fields`): conserva accesos, pero no es `@volatile` ni hace atómicas las
operaciones.

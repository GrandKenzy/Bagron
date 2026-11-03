# 04. Atributos de layout y `volatile`

Los decoradores de layout se aplican al agregado:

```bg
@packed
@align(8)
struct Packet:
    tag: byte
    length: uint32
```

`@packed` reduce el padding entre campos y `@align(N)` solicita una alineación
mínima. Deben elegirse según la ABI o el formato que se está representando;
no son optimizaciones intercambiables.

Para registros de hardware puede declararse un agregado `volatile`:

```bg
volatile struct UART:
    status: uint32
    control: uint32
```

`volatile` conserva las lecturas y escrituras del agregado. No hace atómicas
las operaciones, no verifica la dirección MMIO y no sustituye a `@unsafe` al
usar un puntero cuya procedencia no puede demostrarse.

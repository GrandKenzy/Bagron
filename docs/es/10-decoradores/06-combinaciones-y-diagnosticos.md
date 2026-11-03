# 06. Combinaciones y diagnósticos

Los decoradores se validan en el nivel donde aparecen. Estas combinaciones no
son válidas:

```bg
@static
func helper() int32:                 # @static necesita una clase
    return 0

@after
func update(value: int32) void:      # @after necesita un hook de acceso
    return

@order_msb
struct Packet:                        # solo funciona con flags
    value: uint8

@unknown
func bad() void:                      # no hay decoradores arbitrarios
    return
```

En una clase, `@static`, `@unsafe`, `@assembler`, `@recursive` y `@after` se
validan como decoradores de método. En una función de nivel superior solo son
válidos `@unsafe`, `@assembler` y `@recursive`. `@frozen` solo pertenece a la
declaración `class`; `@packed`, `@align(N)` y `@order_msb` solo a agregados.

No repitas un decorador:

```bg
@unsafe
@unsafe
func duplicated() void:
    return
```

El compilador también rechaza los parámetros de `@align` que no sean una
potencia de dos entre `1` y `64`, más de un `@align` en el mismo agregado y
`@order_lsb`.

## Combinaciones permitidas

Una función puede combinar `@unsafe`, `@assembler` y `@recursive` si cada
contrato tiene sentido. Un método puede añadir `@static` o `@after` según su
caso; `@after` sigue reservado a los hooks. Una clase puede ser `@frozen` y
contener métodos `@unsafe`, pero sus atributos siguen sujetos a la regla de
inicialización.

Los decoradores no sustituyen las comprobaciones de la firma. Por ejemplo,
`@unsafe` no permite omitir `Len_t`/`Size_t` de un array, y `@recursive` no
autoriza devolver un puntero local.

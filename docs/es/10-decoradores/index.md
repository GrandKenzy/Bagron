# Decoradores y contratos

## Índice

- [01. Inventario y sintaxis](01-inventario-y-sintaxis.md)
- [02. Seguridad, recursión e `inline`](02-seguridad-recursion-e-inline.md)
- [03. Ensamblador](03-assembler.md)
- [04. Métodos y clases](04-metodos-y-clases.md)
- [05. Layout de agregados](05-layout-de-agregados.md)
- [06. Combinaciones y diagnósticos](06-combinaciones-y-diagnosticos.md)

Los decoradores cambian reglas que el compilador valida.

| Decorador | Se aplica a | Efecto |
| --- | --- | --- |
| `@unsafe` | funciones | permite procedencia o indexación no demostrable |
| `@assembler` | funciones | habilita `#assembler`; implica `unsafe` |
| `@recursive` | funciones | acepta ciclos no convertibles a tail recursion |
| `inline` | funciones | especificador de firma, no decorador `@`; solicita expansión en perfiles optimizados |
| `@packed` | agregados | reduce padding |
| `@align(N)` | agregados | solicita alineación entre 1 y 64 |
| `@order_msb` | `flags` | coloca bitfields desde el extremo MSB |
| `@frozen` | clases | limita escrituras a inicializadores |
| `@after` | hooks de clase | ejecuta hooks después del acceso |

Una función segura no puede llamar a una `@unsafe`; el decorador tampoco
convierte enteros en booleanos ni elimina las comprobaciones de `Null` o de
arrays.

```bg
@recursive
func factorial(value: int32) int32:
    if value == 0:
        return 1
    return value * factorial(value - 1)
```

La recursión directa de cola puede convertirse en un bucle sin `@recursive`.
Los decoradores de layout solo se aceptan en los agregados correspondientes;
LSB es el orden predeterminado y `@order_msb` la única alternativa explícita.

`inline` y `volatile` son palabras reservadas con posición propia en la
sintaxis, no forman parte del inventario de decoradores `@...`. Un nombre
desconocido después de `@` se rechaza; no hay alias silenciosos ni decoradores
de compatibilidad.

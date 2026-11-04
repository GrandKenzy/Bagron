# 01. Inventario y sintaxis

Bagron distingue decoradores de función, de método, de clase y de agregado.
Todos usan `@nombre` en una línea propia antes de la declaración:

```bg
@unsafe
func read(pointer *: int32) int32:
    return (pointer)
```

El inventario válido es:

| Decorador | Declaración permitida |
| --- | --- |
| `@unsafe` | función y método; también el iniciador de una clase |
| `@assembler` | función y método |
| `@recursive` | función y método |
| `@static` | método de clase |
| `@after` | `__ongetter__` y `__onsetter__` |
| `@frozen` | clase |
| `@packed` | `class`, `struct`, `mold` y `flags` |
| `@align(N)` | `class`, `struct`, `mold` y `flags` |
| `@order_msb` | `flags` |

Un decorador repetido o desconocido produce un diagnóstico. `@order_lsb` no
existe: LSB ya es el orden predeterminado.

No confundas estos elementos relacionados:

- `inline` es un especificador antes de `func`, no `@inline`;
- `volatile` es un calificador antes de `struct`, `mold` o `flags`, no
  `@volatile`;
- `unique` es un calificador de tipo y `public`/`private` son modificadores de
  declaración, no decoradores.

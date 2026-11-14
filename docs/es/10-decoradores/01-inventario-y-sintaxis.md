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
| `@consume` | función (no método); consume sus parámetros `opaque` |
| `@static` | método de clase |
| `@after` | `__ongetter__` y `__onsetter__` |
| `@before` | `__deletion__` (ejecuta el hook antes de la limpieza automática de memoria) |
| `@frozen` | clase |
| `@packed` | `class`, `struct` y `mold` |
| `@align(N)` | `class`, `struct` y `mold` |
| `@signed` | `fields` |

Un decorador repetido o desconocido produce un diagnóstico. `fields` solo
acepta `@signed`.

No confundas estos elementos relacionados:

- `inline` es un especificador antes de `func`, no `@inline`;
- `volatile` es un calificador antes de `struct`, `mold` o `fields`, no
  `@volatile`;
- `unique` es un calificador de tipo y `public`/`private` son modificadores de
  declaración, no decoradores.

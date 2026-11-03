# Changelog 1.0.1

## Tipos

- **Target-sized integer widening (`usize` and `isize`)**:
  Safe implicit widening is now permitted from smaller and equal-width integer types into target-sized pointer scalars (`usize` for unsigned integers, `isize` for signed integers) whenever `sizeof(source) <= sizeof(target)`.
  - Unsigned integers (`uint8`, `uint16`, `uint32`, and `uint64` on 64-bit platforms) widen implicitly to `usize` in variable assignments, return statements, and function argument evaluation.
  - Signed integers (`int8`, `int16`, `int32`, and `int64` on 64-bit platforms) widen implicitly to `isize`.
  - Implicit narrowing remains prohibited: assigning `usize` or `isize` back to smaller or fixed-width integer types without validation raises a compilation error.
  - The raw `byte` type remains isolated and does not implicitly widen to `usize`.

## Léxico y Sintaxis

- **Coma final opcional en `enum`**:
  Los miembros dentro de un bloque `enum` se delimitan por comas, pero la coma final en el último miembro ahora es opcional.
  ```bg
  enum Token uint8:
      IDENT = 0
  ```
  Las declaraciones con múltiples miembros pueden omitir la coma en el último elemento (por ejemplo, `A = 0, B = 1`) o conservarla (`A = 0, B = 1,`).

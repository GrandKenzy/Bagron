# Changelog 1.0.1

## Types

- **Target-sized integer widening (`usize` and `isize`)**:
  Safe implicit widening is now permitted from smaller and equal-width integer types into target-sized pointer scalars (`usize` for unsigned integers, `isize` for signed integers) whenever `sizeof(source) <= sizeof(target)`.
  - Unsigned integers (`uint8`, `uint16`, `uint32`, and `uint64` on 64-bit platforms) widen implicitly to `usize` in variable assignments, return statements, and function argument evaluation.
  - Signed integers (`int8`, `int16`, `int32`, and `int64` on 64-bit platforms) widen implicitly to `isize`.
  - Implicit narrowing remains prohibited: assigning `usize` or `isize` back to smaller or fixed-width integer types without validation raises a compilation error.
  - The raw `byte` type remains isolated and does not implicitly widen to `usize`.

## Lexing and Syntax

- **Optional trailing comma in `enum`**:
  Members within an `enum` block are delimited by commas, but the trailing comma on the last member is now optional.
  ```bg
  enum Token uint8:
      IDENT = 0
  ```
  Declarations with multiple members can omit the comma on the last element (e.g. `A = 0, B = 1`) or retain it (`A = 0, B = 1,`).

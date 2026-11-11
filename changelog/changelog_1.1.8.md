# Changelog 1.1.8

## Enums

- Enum members are now available as typed compile-time constants such as
  `Estado.ACTIVO` in initializers, function arguments, returns, and comparisons.
- Signed enums accept negative explicit member values, and enum constants can
  initialize global variables using their scalar ABI representation.
- Enum members preserve the enum's nominal type; implicit conversion to the
  integer base and mixing different enum types remain rejected.

## Buffer

- Fixed fixed-capacity buffer literals so their byte count must exactly match
  the declared `buffer[N]` capacity; mismatches are rejected during semantic
  validation instead of being silently zero-filled or emitted out of bounds.

## Ownership diagnostics

- Length and exclusive-region diagnostics now explain the `Len_t` and
  `Region_t` contracts and suggest valid ways to propagate them without
  weakening ownership checks.

## Release

Released as Bagron `1.1.8` on 2026-11-11.

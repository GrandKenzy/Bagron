# Changelog 1.1.9

## Modules

- Modules under `modules/` may now be organized in nested folders without
  changing their import names. The `.bg` filename remains the logical module
  name, and duplicate logical names are rejected as ambiguous.
- Source libraries support the same recursive module layout.

## Integer Types and Limb Aggregates

- Removed `uBint`, `flags`, and the legacy `Bint<...>` spelling.
- Added structural `fields` aggregates with positional `Bint(n)` limbs and
  optional `@signed` metadata.
- Added public module directives `#defint` and `#defuint` for LLVM-supported
  scalar integer widths.

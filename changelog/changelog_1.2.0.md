# Changelog 1.2.0

## Libraries

- Named global libraries may omit `as Alias`; the library name is used as the
  namespace, while quoted library paths still require an explicit alias.

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
- Fixed signedness preservation when a `#defuint` value is returned from a
  function and then compared or coerced.
- Invalid integer directives no longer alter the intrinsic type set used by a
  later compilation.

## Preprocessor

- Added `#endif` as the dedicated terminator for conditional `#if` blocks.
  The `#end` directive remains reserved for `#assembler` blocks, removing the
  ambiguity between conditional and assembler terminators.

## Functions and assembler

- Removed `return asm`; `#assembler` blocks now use an implicit ABI return.
- `void` and `Never` functions may omit an explicit `return`.

## Compiler members and ownership

- Replaced the source-level `Len_t`, `Size_t`, `Signed_t`, and `Region_t`
  parameters with the read-only compiler members `.<len>`, `.<size>`, and
  `.<region>`.
- Compiler members derive array, chain, buffer, scalar, and aggregate metadata
  from the value being inspected. Calls keep only their explicit source
  arguments.
- Added field-aware ownership tracking for resource-bearing aggregates. Unique
  borrows distinguish disjoint struct fields, while moved or closed aggregate
  resources remain invalid on every affected path.
- `@consume` functions now must close or transfer every owned opaque parameter
  before leaving, and opaque globals cannot be consumed from a function.
- Volatile mold literals preserve observable volatile stores for both temporary
  clearing and active-member initialization.
- Updated the compiled-library signature format so libraries built against the
  retired metadata-parameter ABI are rejected and must be rebuilt.

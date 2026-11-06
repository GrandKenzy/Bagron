# Changelog 1.1.1

## Preprocessor

- Added the `ARCHB` preprocessor condition for selecting target code by its
  canonical 32-bit or 64-bit architecture width.

## Syntax

- Added one-line bodies for ordinary functions and class methods. A function
  may now place exactly one call, `return`, `pass`, or `Del` statement after
  its signature colon.
- Preserved the existing `FUNCTION_BODY` AST shape and indented-body syntax.
  Inline bodies still reject control flow, declarations, ASM blocks, and
  multiple statements.
- A `void` function may finish after one inline call; value-returning functions
  still require an explicit `return`, with no implicit return introduced.
- Rebuilt the Gram AOT parser so its grammar identifier matches the updated
  frontend grammar.

## Aggregate Literals

- Added designated aggregate literals for `struct`, `mold`, and `flags`, such
  as `Point{ .x = 20, .y = 40 }`.
- Struct and flags literals zero omitted fields; a mold literal requires
  exactly one active member.
- Preserved postfix reads on temporary literals while rejecting assignments and
  address-taking through a temporary member.
- Local designated aggregate initialization now skips the redundant default
  store before writing the completed literal value.
- Cleared inactive `mold` bytes and masked signed `flags` fields before their
  bit shift, preventing stack-data exposure and neighboring-bit corruption.
- Preserved nominal aggregate identity through imported type aliases.

## Standard Library

- Removed forced inlining from stateful I/O, formatting, and clock bodies;
  only small pure predicates and thin forwarding wrappers remain explicitly
  inline in `standard`.

## Security

- Added a `usize` overflow guard before allocating and copying a concatenated
  `buffer`, trapping instead of allowing the wrapped size to cause an
  undersized allocation.
- Rejected local or unknown pointer provenance hidden inside returned
  aggregates, and prevented local addresses from escaping into global
  aggregate storage.
- Safe functions can now index fixed-size arrays with an unsigned index proven
  below a literal bound from `while` conditions or numeric `for` ranges.

## Release

- Released as Bagron `1.1.1` on 2026-11-05.

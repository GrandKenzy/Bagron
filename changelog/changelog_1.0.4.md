# Changelog 1.0.4

## Compiler Safety Contract

Version 1.0.4 prepares the compiler for low-level byte and integer code without
opening a general unchecked-cast or raw-memory escape hatch.

- Define modular arithmetic for fixed-width unsigned integers (`uint8`,
  `uint16`, `uint32`, and `uint64`), including `uint32` modulo `2^32` and
  `uint64` modulo `2^64`.
- Keep compile-time constant folding consistent with the generated runtime
  operations and reject integer literals that do not fit their declared type.
- Define safe shift behavior:
  - constant shift counts greater than or equal to the operand width are
    compilation errors;
  - dynamic invalid shift counts trap instead of relying on undefined or
    target-specific LLVM behavior.
- Add explicit, scalar-only conversions between `byte` and `uint8`.
  Conversions remain opt-in; implicit mixing, pointer conversion, array
  conversion, and general-purpose casts remain rejected.
- Add a restricted `secure_clear(data)` compiler intrinsic for mutable
  `byte[]` and `buffer[]` storage. It emits volatile byte stores and preserves
  bounds, ownership, and borrow-checker rules.
- Formalize `@packed` and `@align(N)` for `class` declarations. Classes keep
  their method, inheritance, and hook semantics while using the existing
  struct-backed layout rules; packed inheritance remains restricted to packed
  parents.
- Make the Gram AOT frontend select `System` and `Arch` clauses after target
  preprocessing, avoiding textual first-clause selection on Linux and adding
  an explicit diagnostic for unsupported macOS targets.
- Add the compiler-owned `extern bagron` process ABI for `__bagron_argc()` and
  `__bagron_arg_copy(...)`. The native wrapper stores `argc`/`argv` in private
  globals, validates indices and destination capacity, and does not add a
  linker dependency.
- Regenerate and ship the Gram AOT parser with the current class and aggregate
  decorator grammar, including `@packed class` support.
- Fix Windows source-mode launchers to resolve both portable runtimes at
  `.runtime\python.exe` and virtual-environment runtimes at
  `.runtime\Scripts\python.exe`.

## Existing Language-Level Scope

The following operations remain expressible in Bagron source and do not require
new native escape hatches:

- masks and bitwise expressions;
- rotations built from shifts and OR after validating the shift count;
- endian-aware integer reads and writes over byte arrays;
- bounded byte copying, comparison, and ordinary memory filling;
- `mold` for deliberate overlapping memory views and representation layouts.

## Compatibility and Security

- `mold` remains available for layout reinterpretation; it is not replaced by
  the scalar `byte`/`uint8` conversion.
- No general `cast`, arbitrary LLVM `bitcast`, raw pointer arithmetic, or
  unchecked `memcpy`/`memset` primitive is introduced.
- Existing `@unsafe`, array bounds, buffer ownership, borrow checking, pointer
  provenance, and target-specific layout rules remain enforced.
- The compiler changes must be covered by focused light tests for arithmetic
  boundaries, shift diagnostics, scalar conversions, and safety restrictions;
  IR/backend checks for secure clearing belong to the aggressive suite.

## Non-Goals

- This release does not add cryptographic algorithms or a cryptography
  library.
- Rotations, endian helpers, and ordinary byte utilities remain source-level
  building blocks rather than compiler intrinsics.

## Release

Released as Bagron `1.0.4` on 2026-11-03.

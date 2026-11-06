# Changelog 1.1.2

## Libraries

- Source library validation now uses the target clauses and `library`
  dependencies declared by the package's `main.bg`. Packages without a
  `main.bg` validate with automatic host target selection.
- Conditional clauses and library directives in a source package are selected
  before its metadata and frontend snapshot are generated.

## Ownership and Borrow Checker

- Added the `@consume` function decorator. A function marked with it takes
  ownership of every `opaque` argument it receives and leaves the caller's
  binding `closed`; its own `opaque` parameters are `owned` inside the body, so
  they can be closed or forwarded to another `@consume` function. `@consume`
  requires at least one `opaque` parameter and is not available on methods.

  ```bg
  @consume
  func release(handle: FD) void:
      return
  ```

- The `close_*` naming convention still consumes descriptors for compatibility
  and remains the only option for `extern` functions, which cannot carry
  decorators. A Bagron function that relies on it without `@consume` now emits
  a warning.
- Copying or assigning a named `opaque` descriptor (`g: FD = h`, `g = h`) now
  moves its ownership: `g` becomes `owned` and `h` becomes the new `moved`
  state, so closing or using `h` afterwards is a compile-time error. This
  closes a double-close hole through aliases. Borrowed parameters and global
  descriptors cannot be moved.
- Closing or moving, inside a loop, a descriptor declared outside that loop is
  rejected, matching the existing `Del` restriction. A descriptor declared
  inside the loop body may still be consumed in the same iteration.
- Returning an `opaque` descriptor transfers its ownership to the caller; only
  an `owned` local or `@consume` parameter may be returned.
- Conditional branches that always exit (`return`, `break`, `continue`, or a
  `Never` call) no longer poison the ownership state of the code after the
  branch.
- Consuming a `buffer` or `opaque` descriptor on only some conditional paths
  produces a specific conditional-consumption diagnostic, and a `dead` buffer
  can be reconstructed in place (`data = 0`, `data = {...}`, or `left + right`)
  after `Del`.
- Unfreed local `buffer`s and unclosed `opaque` descriptors leaving scope or hit
  by an early `return` now emit a leak warning. Passing `--strict-ownership`
  turns leak warnings into compilation errors.

## Classes and Destruction

- `Del instance` now automatically zeroes all memory bytes of the class instance.
- By default, memory zeroing happens before executing the `__deletion__` hook.
- Added the `@before` method decorator for `__deletion__`, allowing the deletion hook
  to execute prior to the automatic memory zeroing when fields must be inspected or
  released before cleanup.

## Compiler Analysis

- Added a conservative definite-write analysis for one-dimensional fixed local
  arrays. It tracks constant element writes, complete branch intersections, and
  statically bounded `for` ranges, while rejecting unknown reads and escapes.
  The LLVM backend now consumes proven results in `prod`/`high` profiles to
  omit redundant local zero-initialization; `dev` and unproven arrays retain
  their previous deterministic initialization.
- Added conservative summaries for fixed-array parameters of private Bagron
  functions. Calls to helpers that overwrite every element before reading it
  can now treat the argument as scratch storage, while input arrays, external
  calls, public calls, and ambiguous escapes still require their established
  initialization guarantees.
- Hardened the array-flow proof for compound expressions and numeric-loop
  recurrences. Dynamic indexes such as `data[i - 1]` are no longer mistaken
  for constants, while safe backward dependencies such as SHA-256's
  `schedule[i - 16]` can be proven from earlier loop writes. This removes the
  redundant schedule zeroing in the laboratory SHA-256 build.

## Standard Library Boundaries

- Removed the obsolete repository-level `modules/io.bg`. High-level I/O now
  lives in `BagronLab/io` and selects the target-native `windows.lib` or
  `gnulibrary.lib` dependency from its own library entry point.

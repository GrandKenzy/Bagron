# Changelog 1.1.2

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

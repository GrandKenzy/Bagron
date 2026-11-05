# Changelog 1.1.0

## Clauses

- Added `Bagron --version` (and `Bagron -V`) to report the compiler version
  directly from the canonical project metadata.

- Imported modules now inherit omitted target clauses from the entry module.
- Removed warnings for imported modules that do not declare `System`, `Arch`,
  or `Boot`; these modules use the effective target selected by `main.bg`.
- Explicit target clauses declared by imported modules are validated against
  the entry module, and incompatible declarations now terminate compilation.
- Partial target declarations inherit their omitted dimensions without
  changing the global backend target.
- System and architecture aliases are now normalized through one platform
  catalog. Known but unsupported platforms are reported explicitly instead of
  being confused with a supported target.
- Android targets are now accepted with explicit `System "android"` and
  `aarch64-linux-android<api>` or `x86_64-linux-android<api>` triples. The LLVM
  backend produces native ELF executables through the configured Android NDK;
  APK packaging and automatic emulator execution are not included yet.
- LLVM class access hooks and `__frontend__` initializers now resolve source-
  level nominal names after LLVM mangling, restoring their backend emission.
- Updated the related tests, project map, and documentation to describe the
  inheritance and compatibility rules formally.

## ABI & Baremetal

- Added the explicit `ABI` clause with `sysv_amd64` as its only supported
  value.
- Baremetal projects now require `ABI "sysv_amd64"`; ABI declarations are
  rejected for Linux, Windows, and other non-Baremetal targets.
- Imported modules inherit the entry module's ABI when omitted, while explicit
  incompatible ABI declarations stop compilation.
- Baremetal assembler preparation uses System V AMD64 only after explicit ABI
  selection and keeps LLVM's default AMD64 C calling convention.

## Bagron Installer

- POSIX launchers now resolve their installation symlink before locating the
  portable Python runtime, so `~/.local/bin/bagron` works correctly.
- Added a regression test that invokes the launcher through a symlink and
  verifies the caller directory, runtime location, and forwarded arguments.
- Installations now rebuild the Gram AOT/FFI parser for the current platform
  instead of reusing or distributing precompiled `build/aot` artifacts.
- Rebuilds clear only the installation's AOT output directory, preventing
  stale libraries and manifests from being mixed across Gram versions.

## Libraries

- Platform-specific `library` directives are now selected after conditional
  preprocessing, so inactive dependencies such as `windows.lib` and
  `gnulibrary.lib` are not loaded together.
- Lib1 packages can resolve imports between their own extracted source
  modules without escaping the registered package root.
- Lib1 packages preserve and restore serialized `@assembler` blocks when they
  are consumed, so packaged native functions retain their assembly body and
  return contract.
- Assembly-block association is scoped by source module, preventing a local
  wrapper such as `read` from being confused with a packaged native function
  such as `Gnu.read`.
- Lib2 packages declaring `Arch "auto"` now inherit the host architecture
  instead of failing validation against the resolved `x86_64` target.

## Assembler

- Functions marked with `@assembler` from the same `.bg` source now share one
  generated assembly unit and one native object, while imported source files
  remain isolated.
- Assembly diagnostics map generated line ranges back to the original source
  function and line, and repeated non-local labels are rejected before Clang.
- `Never @assembler` functions no longer receive an implicit `ret`; their
  assembly body must guarantee that control does not fall through, while
  `void` and value-returning assembler functions retain their existing return
  behavior.

## Standard Modules

- Migrated the laboratory `standard` modules away from per-module system ABI
  declarations. Windows modules now consume `windows.lib`, while Linux modules
  consume `gnulibrary.lib` through the platform-selected dependencies in
  `standard/main.bg`.

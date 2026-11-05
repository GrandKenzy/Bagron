# Changelog 1.1.0

## Clauses

- Imported modules now inherit omitted target clauses from the entry module.
- Removed warnings for imported modules that do not declare `System`, `Arch`,
  or `Boot`; these modules use the effective target selected by `main.bg`.
- Explicit target clauses declared by imported modules are validated against
  the entry module, and incompatible declarations now terminate compilation.
- Partial target declarations inherit their omitted dimensions without
  changing the global backend target.
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

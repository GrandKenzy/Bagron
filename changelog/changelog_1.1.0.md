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

## Bagron Installer

- POSIX launchers now resolve their installation symlink before locating the
  portable Python runtime, so `~/.local/bin/bagron` works correctly.
- Added a regression test that invokes the launcher through a symlink and
  verifies the caller directory, runtime location, and forwarded arguments.

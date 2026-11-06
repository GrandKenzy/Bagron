# Changelog 1.1.3

## Library Resolution

- Added unquoted global library names such as `library gnulibrary as gnu`.
  Bagron resolves these names only in `BAGRON_ROOT/libs/<name>.lib`; quoted
  paths continue to resolve only in the project's `libs/` directory.

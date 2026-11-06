# Changelog 1.1.4

## Installer and Releases

- Compiled Windows and Linux installers now carry the portable Python runtime,
  vnma, Gram, llvmlite, the AOT parser, and validated Bagron library packages.
- Added offline installation smoke coverage for `bagron --version` and native
  example compilation.
- Added clean `bagron --uninstall` handling and stable GitHub release updates
  through `bagron --update`.

## Library Resolution

- Added unquoted global library names such as `library gnulibrary as gnu`.
  Bagron resolves these names only in `BAGRON_ROOT/libs/<name>.lib`; quoted
  paths continue to resolve only in the project's `libs/` directory.

## CLI

- Simplified `bagron --help` and library usage output to expose only the public
  `bagron` commands.

## VS Code Extension

- Release payloads include the validated Bagron VS Code extension so it can be
  installed directly with `bagron --vscode install`.

## Release

- Released as Bagron `1.1.4` on November 6, 2026.

# Changelog 1.0.2

## Modules and Linking

- **Search in base Bagron directories (`modules/` and `libs/`)**:
  - `import`: Now checks the canonical `modules/` and `libs/` directories located in the Bagron installation root (`BAGRON_ROOT`), allowing external projects to consume standard modules (`string`, `asmutils`, `io`, etc.) without copying them locally.
  - Standard imported modules can in turn import sibling modules within Bagron without triggering out-of-root module errors.
  - `#link`: The `#link "<path>"` directive now checks within the local project and, if not found locally, searches in `BAGRON_ROOT / 'libs'`, `BAGRON_ROOT / 'modules'`, or the Bagron root (including `bagron/<subfolder>` prefixes).
  - `mangling`: Internal symbol keys for modules originating from `BAGRON_ROOT` are normalized canonically and deterministically relative to the installation root.

## Standard Library

- Standard modules added to `modules/` in the Bagron repository:
  - `string.bg` (safe and cross-platform chain utilities with execution trap validation)
  - `asmutils.bg` (cross-platform abstractions for execution traps and breakpoints)
  - `alphabet.bg`, `io.bg`, `math.bg`, `mem.bg`, `mmap.bg`, `os.bg`, `time.bg`

## Semantic Resolution and Methods

- **Module function calls from homonymous methods**:
  - Fixed call resolution so that when a class method invokes a free or external function with the same name (such as `connect(...)` inside `Socket.connect`), the call resolves to the module-level function instead of being intercepted as implicit recursion on the method.
  - `Storage.resolve_function_for_module` and `Storage.resolve_variable_for_module` now consistently query the root module storage (`_module_root()`) and canonicalize paths across Windows and Linux.

## Packaging and Documentation

- Installer and project template metadata are aligned with version `1.0.2`.
- Added documentation for installing the bundled VS Code extension with `Bagron --vscode install`, the VS Code command palette, or `code --install-extension`.
- The bundled VSIX metadata now reports version `1.0.2`.

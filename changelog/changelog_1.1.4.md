# Changelog 1.1.4

## Library Resolution and Packaging

- **Transitive Library Dependencies**: Library packages declaring dependency directives in their root `main.bg` (such as target layers like `library "windows.lib" as Win` or `library "gnulibrary.lib" as Gnu`) now have those dependencies automatically resolved and loaded when consumed by another module or application. Quoted library directives inside extracted packages search the package's own `libs/` directory and fall back to the canonical Bagron library path.
- **Export Symbol Isolation**: Packaging a library with `bagron library` now strictly isolates public symbols to the modules belonging to the library being built. Dependency symbols from intermediate build directories or nested packages are no longer leaked into the parent package's public export table, preventing unresolved symbol errors when consumers import the library.

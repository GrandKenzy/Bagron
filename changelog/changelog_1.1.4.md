# Changelog 1.1.4

## Standard Library Distribution

- Bagron installations no longer publish a global `modules/` directory. Standard APIs are consumed as complete `.lib` packages from `libs/`; local project modules and modules embedded inside `lib1` sources remain supported.

## Library Resolution and Packaging

- **Transitive Library Dependencies**: Library packages declaring dependency directives in their root `main.bg` (such as target layers like `library "windows.lib" as Win` or `library "gnulibrary.lib" as Gnu`) now have those dependencies automatically resolved and loaded when consumed by another module or application. Quoted library directives inside extracted packages search the package's own `libs/` directory and fall back to the canonical Bagron library path.
- **Export Symbol Isolation**: Packaging a library with `bagron library` now strictly isolates public symbols to the modules belonging to the library being built. Dependency symbols from intermediate build directories or nested packages are no longer leaked into the parent package's public export table, preventing unresolved symbol errors when consumers import the library.

## CLI

- **Library Signing and Metadata Verification (`bagron sign` / `bagron verify`)**: Added first-class signing and integrity verification for Bagron libraries:
  - `bagron sign <dir>` computes a canonical SHA-256 signature binding the source `.bg` files with metadata (`author`, `name`, `version`) and records it in `meta.toml` under `[author].signature`.
  - `bagron verify <dir>` checks that the sources and metadata of a library directory match the signature declared in `meta.toml`.
  - `bagron library` automatically reads `meta.toml` to default `--name` and `--version` if omitted, and automatically signs/refreshes `meta.toml` when packaging.
  - `bagron install` validates `meta.toml` signatures when packaging from source directories to protect against altered or corrupted packages.
- **Caller Working Directory Path Resolution**: Library commands (`bagron library`, `bagron inspect`, `bagron verify`, and `bagron unpack`) now resolve relative input source paths and output destination paths against the caller's working directory (`cwd` / `BAGRON_CALLER_DIR`) instead of falling back to the compiler installation directory.
- **Local Installation Command (`bagron install`) [Temporary]**: Added a temporary `bagron install` command to install libraries and modules directly into project-local directories, replacing existing targets:
  - `bagron install --library --v1 <source>` builds (or copies) and installs a `lib1` library package into the local `libs/` directory.
  - `bagron install --library --v2 <source>` compiles and installs a `lib2` library package into `libs/`.
  - `bagron install --module <source.bg|dir>` installs a source module or module folder directly into the local `modules/` directory.
  *Note: This command is currently provided as a temporary convenience for local workflow management and may evolve in future releases.*
- **Hosting Repository Synchronization (`bagron build --hostutils`)**: Added CLI automation for multi-package hosting monorepositories:
  - Scans `build/` artifacts, compares SHA-256 hashes against `discentra_central/manifest.toml`, and interactively prompts for new semantic versions only for modified packages.
  - Automatically identifies library formats (`lib1` vs `lib2`), sizes, hashes, and canonical cryptographic signatures.
  - Consumes metadata from `discentra_central/manifest.json` to atomically synchronize `discentra_central/packages.toml` and `discentra_central/manifest.toml`.
  - Supports `--auto-patch` for non-interactive CI/CD bumping, `--dry-run` for previews, and `--set-version PKG=VER` for explicit version assignment.
- **Central Package Registry Integration (`bagron package install` / `info` / `search`)**: Added first-class commands to discover, inspect, and download packages from the official Central registry:
  - `bagron package install <name>[@version]` resolves packages from Central, authenticates downloads with official CLI client credentials, verifies SHA-256 integrity checksums, and installs `.lib` packages directly into the local `libs/` directory.
  - `bagron package info <name>[@version]` queries Central and displays comprehensive package metadata, including author, target architecture, format, license, and download statistics.
  - `bagron package search <query>` performs searches across the public Central package catalog.

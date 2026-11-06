# Changelog 1.1.3

## Release Workflow

- Release packaging jobs now prepare their own Python 3.14 runtime, install
  `vnma`, and resolve Gram and `llvmlite` before building the installer.
- Each platform's packaging job builds Gram AOT/FFI from Gram's `main` branch,
  retaining its native library and matching `gram_parser_manifest.json`.
- Added a release-payload assembly step that collects compiler sources, local
  vendored dependencies, Gram AOT, and metadata for PyInstaller to embed
  alongside the portable Python runtime.
- Added post-packaging installation smoke tests for Linux and Windows that
  invoke the built installer, check `bagron --version`, and compile a `.bg`
  example from the installed compiler.
- Release jobs fail when required payload files, compiled parser artifacts, or
  compilation tests are missing or invalid.
- Added manual preview builds through `workflow_dispatch` without publishing a
  GitHub release; tagged releases also check that the tag matches the compiler
  version before packaging.

## Bagron Installer

- Added a prebuilt installation path that extracts the packaged compiler and
  dependencies without cloning Gram, running `vnma install`, or rebuilding the
  AOT parser on the user's machine.
- The installer validates bundle metadata, the AOT grammar identifier and the
  SHA-256 of the packaged native parser before writing compiler files.
- Kept the source/development installation path available for local builds and
  dependency rebuilds; compiled installers no longer fall back to a network
  installation when the prebuilt payload is absent or invalid.
- Preserved the user-local `bagron` launchers and isolated runtime layout
  without changing global Python installations.
- Documented that offline installation still requires an external Clang/LLD
  toolchain (and Android NDK when targeting Android) for native compilation.

## Portable Python Runtime

- Preserve or reconstruct Linux runtime symlinks so aliases such as
  `python`, `python3`, and `python3.14` do not introduce unnecessary
  duplicate executable data.
- Deduplicate compatible shared-library aliases without changing their
  required loader names or runtime resolution.
- Handle Windows runtime aliases separately when symlinks are not appropriate.
- Verify that runtime deduplication survives PyInstaller packaging and
  extraction, and that the bundled Python and `pip` remain usable.

## Reproducibility and Verification

- Keep Gram on its upstream `main` branch while tagged versions are not
  available; check the generated AOT library and grammar manifest against
  the compiler before packaging.
- Preserve dependency version and build provenance metadata in release
  artifacts, including the Gram AOT grammar identifier.
- Test installation without network access after the artifact is downloaded,
  followed by `bagron --version` and compilation of a minimal `.bg` example.
- Check release artifact size, verify executable and shared-library aliases,
  and retain regression coverage for online source installations.

## Release

- Pending: Bagron `1.1.3` has not been released. Record the release date only
  after the packaged installers and verification tests pass.

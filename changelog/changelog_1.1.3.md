# Changelog 1.1.3

## Release Workflow

- Prepare platform-specific release environments for Linux x86-64 and Windows
  x86-64 using `vnma` during GitHub Actions packaging jobs, instead of leaving
  dependency resolution to the installed user's machine.
- Build the Gram AOT/FFI parser for each release target and package the native
  library together with its matching `gram_parser_manifest.json`.
- Include the Bagron compiler sources, the selected `llvmlite` distribution,
  Gram dependencies, and the portable Python runtime in each release artifact.
- Retain platform-specific tests and smoke compilation before publishing
  artifacts; add installation smoke tests against the actual packaged release.
- Make the release workflow fail if the packaged runtime, dependency set, AOT
  parser, or executable smoke test is missing or incompatible.

## Bagron Installer

- Add a prebuilt installation path that extracts the packaged compiler and
  dependencies without cloning Gram, running `vnma install`, or rebuilding the
  AOT parser on the user's machine.
- Validate the packaged AOT library and grammar manifest before enabling the
  `bagron` launcher; do not silently fall back to a mismatched parser.
- Keep the source/development installation path available for local builds and
  explicit dependency rebuilds.
- Preserve the existing user-local launcher and installation behavior while
  avoiding unnecessary modifications to global Python installations.
- Document that an offline installation of the packaged compiler does not
  automatically imply a fully self-contained native toolchain: external
  Clang/LLD and target-specific SDKs may still be required for compilation.

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

- Pin the Gram revision used by `vnma` and the AOT build so a given Bagron
  release cannot silently pick up incompatible changes from Gram's `main`
  branch.
- Preserve dependency version and build provenance metadata in release
  artifacts, including the Gram AOT grammar identifier.
- Test installation without network access after the artifact is downloaded,
  followed by `bagron --version` and compilation of a minimal `.bg` example.
- Check release artifact size, verify executable and shared-library aliases,
  and retain regression coverage for online source installations.

## Release

- Pending: Bagron `1.1.3` has not been released. Record the release date only
  after the packaged installers and verification tests pass.

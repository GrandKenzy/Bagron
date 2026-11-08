# Changelog 1.1.5

## Release

- Released on 2026-11-07.

## Package Security

- Package installation now rejects unsafe package names, non-HTTPS download URLs, missing or malformed SHA-256 checksums, and artifacts whose destination would escape the target `libs/` directory.
- Remote artifacts are validated before being published through an atomic file replacement. `--allow-unverified` is available only as an explicit development or private-registry override for missing integrity metadata.
- Local source installation now stops on missing or invalid integrity metadata unless `--allow-unverified` is provided.
- Local library names, installation directories, extraction destinations, and cache markers reject path escapes and symbolic-link redirections.
- Central search uses the same bounded HTTPS and redirect policy as package downloads, and malformed catalog responses are rejected.
- Package manifests and lockfiles validate dependency names and edges strictly; concurrent lockfile updates are serialized.

## Package Workflows

- `bagron package install` now keeps an already verified local library instead of downloading or replacing it. `bagron package update <name>` performs the explicit atomic replacement from Central.
- `bagron package list` reports verified local libraries, while `bagron package pull <file-or-directory>` imports local `.lib` artifacts without publishing them to Central.
- `bagron package uninstall <name>` removes a local artifact and its lock entry, but refuses to leave another locked package without a declared dependency.

## Hosting Tools

- `bagron build --hostutils --dry-run` no longer creates build artifacts, hosting directories, or package metadata while previewing a synchronization.
- Hosting metadata files are written through temporary files and atomic replacement.
- Generated library artifacts are verified in a temporary location before they replace an existing build artifact.
- Hostutils now prompts only for packages whose artifact changed, accepts a custom `MAJOR.MINOR.PATCH` version, and uses the next patch when the prompt is left empty. Central publishing is restricted to lib1 packages, and its metadata stays aligned with each package's internal version.

## Libraries and Imports

- Library packages are verified before use, including exact archive contents, native artifact references, safe paths, metadata hashes, and bounded ZIP resources.
- Library extraction is cached by the complete package SHA-256 and revalidated before reuse. Corrupted or incomplete cache entries are rebuilt safely.
- Quoted library paths are isolated to the consuming project or the package that declares them. Source imports no longer fall back to `.bg` files under the global installation.
- Projects can pin direct and transitive library artifacts with `bagron.lock`; package installation updates the lockfile only after the artifact has been verified.

## Central Registry

- Central downloads enforce HTTPS redirects, bounded responses, package identity and format checks, and atomic replacement only after `.lib` verification.
- Central can provide expiring Ed25519/TUF-style metadata that binds each artifact to its name, version, target format, size, and SHA-256 digest.
- Central metadata now rejects non-target statements, invalid versions or lengths, expired metadata, and thresholds that are not met by distinct trusted signatures.
- Central can also publish a complete TUF root, timestamp, snapshot, and targets chain; role thresholds and metadata-version relationships are verified before installation.
- Projects with a lockfile reject Central targets metadata older than the version already accepted for that project.

## Distribution

- Compiled Bagron installers no longer bundle BagronLab `.lib` packages by default. Projects must install their required packages explicitly or provide project-local libraries.
- The release payload still includes an empty `libs/` directory as the stable destination for explicitly installed packages.

## Installer and Package Management

- Windows self-updates no longer launch a visible polling window or depend on `find.exe`; update helpers now wait safely and validate downloaded executable types and HTTPS redirects.
- Prebuilt upgrades are staged and verified before replacing the managed compiler, runtime, and launchers, with rollback on installation failure. Legacy global `modules/` and stale installer dependency locks are not carried into the new installation.
- Source installations validate the bounded GitHub archive before extraction and reject unsafe paths and links; update and bootstrap commands report unsupported host architectures instead of using an incompatible installer.
- `bagron package install` creates a safe empty `libs/` directory before contacting Central, preserves an existing package if lockfile publication fails, and local `.lib` installation requires the requested name and version to match the package metadata.
- POSIX self-updates use a detached shell helper, while unsupported hosts and architectures receive an explicit source-installation message instead of an incompatible binary.

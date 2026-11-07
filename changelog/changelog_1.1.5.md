# Changelog 1.1.5

## Package Security

- Package installation now rejects unsafe package names, non-HTTPS download URLs, missing or malformed SHA-256 checksums, and artifacts whose destination would escape the target `libs/` directory.
- Remote artifacts are validated before being published through an atomic file replacement. `--allow-unverified` is available only as an explicit development or private-registry override for missing integrity metadata.
- Local source installation now stops on missing or invalid integrity metadata unless `--allow-unverified` is provided.

## Hosting Tools

- `bagron build --hostutils --dry-run` no longer creates build artifacts, hosting directories, or package metadata while previewing a synchronization.
- Hosting metadata files are written through temporary files and atomic replacement.

## Libraries and Imports

- Library packages are verified before use, including exact archive contents, native artifact references, safe paths, metadata hashes, and bounded ZIP resources.
- Library extraction is cached by the complete package SHA-256 and revalidated before reuse. Corrupted or incomplete cache entries are rebuilt safely.
- Quoted library paths are isolated to the consuming project or the package that declares them. Source imports no longer fall back to `.bg` files under the global installation.
- Projects can pin direct and transitive library artifacts with `bagron.lock`; package installation updates the lockfile only after the artifact has been verified.

## Central Registry

- Central downloads enforce HTTPS redirects, bounded responses, package identity and format checks, and atomic replacement only after `.lib` verification.
- Central can provide expiring Ed25519/TUF-style metadata that binds each artifact to its name, version, target format, size, and SHA-256 digest.

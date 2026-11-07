# Changelog 1.1.5

## Package Security

- Package installation now rejects unsafe package names, non-HTTPS download URLs, missing or malformed SHA-256 checksums, and artifacts whose destination would escape the target `libs/` directory.
- Remote artifacts are validated before being published through an atomic file replacement. `--allow-unverified` is available only as an explicit development or private-registry override for missing integrity metadata.
- Local source installation now stops on missing or invalid integrity metadata unless `--allow-unverified` is provided.

## Hosting Tools

- `bagron build --hostutils --dry-run` no longer creates build artifacts, hosting directories, or package metadata while previewing a synchronization.
- Hosting metadata files are written through temporary files and atomic replacement.

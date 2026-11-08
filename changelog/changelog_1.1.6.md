# Changelog 1.1.6

## Visual Studio Code support

- The Bagron language extension now exposes a red B icon for .bg files and the extension itself.
- The packaged extension version is 1.1.6 and replaces older copies cleanly during installation.
- Hover, completion, and definition lookup in modules now inherit the `library`
  aliases declared by the owning `main.bg`, including active `#if OS` branches.

## Package management

- `bagron package install`, `update`, `pull`, `list`, and `uninstall` now use
  the installation's `BAGRON_ROOT/libs` directory by default instead of the
  caller's working directory.
- `--select <path>` selects an alternate package directory; `--dir` remains a
  compatibility alias for existing scripts.
- Global package operations keep their lockfile beside the Bagron installation;
  explicitly selected directories keep using the caller project's lockfile.

## Diagnostics

- Library directive errors now show the complete required form,
  `library "ruta.lib" as Alias` or `library nombre_global as Alias`.

## Release

Released as Bagron `1.1.6` on 2026-11-08.

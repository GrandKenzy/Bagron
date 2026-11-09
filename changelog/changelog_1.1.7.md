# Changelog 1.1.7

## Type resolution

- Qualified nominal types such as `Library.Type` are now accepted in variable
  declarations, function signatures, fields, externs, casts, and other type
  positions.
- Qualified types retain the imported library's nominal identity, so values
  returned by functions such as `Library.make_value()` remain compatible with
  their qualified declaration.
- The AOT frontend now reports syntax errors only after consuming the complete
  qualified type spelling.

## Classes

- Typed fields may omit their initializer inside `__init__` or `__frontend__`;
  their storage is initialized to zero, including every byte of fixed arrays.

## Installer

- Fixed the Windows and POSIX launchers so they invoke the installed compiler
  directly instead of recursively starting `vnma run main.py`.

## Release

Released on 2026-11-08.

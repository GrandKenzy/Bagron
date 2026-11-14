# Changelog 1.2.0

## Preprocessor

- Added `#endif` as the dedicated terminator for conditional `#if` blocks.
  The `#end` directive remains reserved for `#assembler` blocks, removing the
  ambiguity between conditional and assembler terminators.

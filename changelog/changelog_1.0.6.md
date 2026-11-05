# Changelog 1.0.6

## Assembler Function Contract

- Replaced `#prep assembler` with `#assembler "intel"` and `#assembler "att"` inside `@assembler` functions.
- Removed the `#prep` directive, the `gas-intel` alias, assembler parameter templates such as `{param}`, and module-level assembler blocks without compatibility aliases.
- Kept `@assembler`, `return asm`, the existing return rules, the automatic ABI status setup, and the prohibition on user-written `ret` instructions.
- Preserved assembler bodies verbatim when passing them to the assembler; Bagron no longer performs textual parameter substitution or instruction-level semantic analysis.

## ABI and Backend Integration

- Reused the existing x86-64 ABI dictionaries to validate supported targets, integer widths, register slots, pointer-sized parameters, and representable stack positions.
- Kept direct register responsibility with the assembler author, including System V and Windows x64 parameter registers and stack locations.
- Updated the GAS emission layer to produce `.intel_syntax noprefix` for `intel` and `.att_syntax prefix` for `att`.
- Removed the obsolete assembler intrinsic and LLVM lowering used for placeholder-based register substitution.

## Diagnostics and Validation

- Added explicit diagnostics for removed syntax, unsupported dialects, module-level assembler blocks, malformed blocks, missing `#end`, invalid ABI targets, unsupported parameter types, and invalid return instructions.
- Preserved the rule that assembler blocks belong to functions and that assembler functions cannot contain regular Bagron statements.

## Documentation and Examples

- Updated the assembler documentation, syntax references, error guidance, examples, and architecture map to describe the direct-ABI-register contract and the Intel GAS dialect name.
- Documented that Clang/GAS remains responsible for validating assembler instructions themselves.

## Tests

- Updated fast and aggressive tests for the new directive syntax, valid dialects, legacy syntax rejection, block closure, return rules, direct ABI registers, raw-body preservation, target validation, and emitted GAS syntax directives.
- Removed module-level assembler coverage and obsolete placeholder-expansion and assembler-intrinsic tests.

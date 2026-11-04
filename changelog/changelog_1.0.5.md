# Changelog 1.0.5

## Explicitly-Typed Class Attributes

Version 1.0.5 introduces explicit type annotations for instance attributes declared within class initializers, eliminating reliance on literal type inference.

- **Explicit attribute typing in initializers (`self.field: Type = value`)**:
  - Class initializers (`__init__` and `__frontend__`) now support explicit type annotations when declaring and initializing instance fields:
    ```bg
    class CRC32:
        func __init__() void:
            self.state: uint32 = 0xFFFFFFFF
    ```
  - Resolves the literal inference limitation where untyped integer constants (such as `0xFFFFFFFF` or `0`) default to `int32`, which previously prevented direct inline initialization of unsigned (`uint32`, `uint64`), narrowed (`uint8`, `byte`), or explicitly typed attributes without artificial helper functions or constructor parameters.
  - Retains full backward compatibility with inferred attribute assignments (`self.field = value`).
  - Statically verifies initializer value compatibility against the declared `TypeSpec` using `is_compatible(...)` at compile time. Incompatible initial values are rejected with diagnostic errors.
  - Restricts typed attribute declarations strictly to class initializers (`__init__` and `__frontend__`). Attempting to use `self.field: Type = value` inside regular methods or standalone functions is rejected during semantic analysis.

## Grammar and AOT Parser Pipeline

- **Gram syntax rules**:
  - Defined `MEMBER_ACCESS_TARGET` (`IDENT . IDENT`) and `FIELD_DECLARATION` (`MEMBER_ACCESS_TARGET : TYPE = VALUE`) in `core/frontend/syntax/items/var_decl.py`.
  - Prioritized `FIELD_DECLARATION` in `FUNCTION_BODY` and `STATEMENT_BODY` before `VAR_ASSIGNATION` to guarantee unambiguous differentiation from local variable declarations (`VAR_DECLARATION`).
- **AOT GIR bridge**:
  - Registered `FIELD_DECLARATION` within `_group_transparent_type` in `core/frontend/aot.py` to lift transparent `TYPE` tokens into structured AST type nodes during deserialization of native Gram GIR buffers.
  - Recompiled and verified the native AOT Gram driver (`bagron_aot.dll`) with the updated grammar tables.

## Backend and Code Generation

- **LLVM place compilation and assignment emission**:
  - Extended LLVM statement emission (`core/backend/llvm/functions/statements.py`) to dispatch `FIELD_DECLARATION` as an assignment statement.
  - Extended memory place resolution (`core/backend/llvm/functions/expressions/memory.py`) to compile `MEMBER_ACCESS_TARGET` places, emitting properly coerced struct GEP and store operations matching the declared field layout.

## Tests and Verification

- Added focused unit tests in `tests/light/test_types.py`:
  - `test_class_field_explicit_type_declaration`: validates syntax, semantic type resolution (`uint32`), LLVM lowering, and executable execution.
  - `test_rejects_incompatible_class_field_type_declaration`: verifies compile-time rejection when the initializer value conflicts with the declared type.
  - `test_rejects_class_field_type_declaration_outside_initializer`: verifies that typed attribute declarations cannot appear outside class initializers.

## Assembler Support for Never Return Type

Version 1.0.5 adds support for non-returning functions decorated with `@assembler` whose return type is `Never`.

- **No return required for Never `@assembler` functions**:
  - Functions declared with `@assembler` and return type `Never` (such as OS exit or process termination primitives) no longer require a `return` or `return asm` statement:
    ```bg
    @assembler
    public func exit(code: int32) Never:
        #prep assembler "att"
            movq $60, %rax
            syscall
        #end
    ```
  - Functions returning `Never` are statically forbidden from using `return` or `return asm`. Attempting to return from a `Never` assembler function produces a compile-time diagnostic.
  - Assembly generation (`core/compiler/prep.py`) omits return status register setup (`mov eax, 1` / `movl $1, %eax`) for `Never` functions, consistent with `void` assembly routines.

## Linux Installer Hardening

- Prevent `install.sh` from accidentally selecting a local `installer.py` when
  invoked through `curl | bash`; the portable ELF installer is now the default.
- Require `BAGRON_LOCAL_INSTALL=1` to opt into source-checkout installation.
- Validate the bundled Python runtime and re-check `pip` after `ensurepip`
  before resolving vnma, Gram, and llvmlite dependencies.

## System V AMD64 ABI Support for `@assembler`

Version 1.0.5 extends `@assembler` template expansion to support the **System V AMD64 ABI** on Linux, ELF, and bare-metal `x86_64` targets.

- **6-register parameter mapping (`RDI`, `RSI`, `RDX`, `RCX`, `R8`, `R9`)**:
  - When targeting Linux (`clause System "linux"` or `x86_64-unknown-linux-gnu`) or ELF triples, `@assembler` parameter placeholders (`{param}`) resolve to the six System V integer/pointer parameter registers across 64-bit (`rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`), 32-bit (`edi`, `esi`, `edx`, `ecx`, `r8d`, `r9d`), 16-bit (`di`, `si`, `dx`, `cx`, `r8w`, `r9w`), and 8-bit (`dil`, `sil`, `dl`, `cl`, `r8b`, `r9b`) widths.
  - Stack arguments starting at the 7th parameter (`index >= 6`) resolve without Windows shadow space, starting directly after the 8-byte return address at `8(%rsp)` (`att`) / `[rsp + 0x8]` (`gas-intel`).
- **Cross-system target triple resolution**:
  - Fixed `_triple_for_request` in `core/backend/llvm/targets.py` so declaring `clause System "linux"` (or `clause System "windows"`) with default `auto` architecture on a different host OS resolves the target triple for the requested OS rather than falling back to the host OS triple.

## Release

Released as Bagron `1.0.5` on 2026-11-03.

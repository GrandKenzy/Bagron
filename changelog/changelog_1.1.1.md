# Changelog 1.1.1

## Syntax

- Added one-line bodies for ordinary functions and class methods. A function
  may now place exactly one call, `return`, `pass`, or `Del` statement after
  its signature colon.
- Preserved the existing `FUNCTION_BODY` AST shape and indented-body syntax.
  Inline bodies still reject control flow, declarations, ASM blocks, and
  multiple statements.
- A `void` function may finish after one inline call; value-returning functions
  still require an explicit `return`, with no implicit return introduced.
- Rebuilt the Gram AOT parser so its grammar identifier matches the updated
  frontend grammar.

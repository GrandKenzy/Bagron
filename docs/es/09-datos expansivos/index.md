# Miembros del compilador

Bagron expone algunos datos derivados del tipo mediante miembros de compilador.
Se escriben con la forma `valor.<miembro>` para distinguirlos de los campos
normales de structs, clases, enums y molds.

## Índice

- [01. Modelo y llamada visible](01-modelo-y-llamada-visible.md)
- [02. Arrays y matrices](02-arrays-y-matrices.md)
- [03. `chain` y `buffer`](03-chain-y-buffer.md)
- [04. Tamaños](04-signed-y-tamanos.md)
- [05. Propagación entre funciones](05-propagacion.md)
- [06. `unique` y procedencia](06-unique-y-region.md)
- [07. ABI y backend](07-abi-y-backend.md)
- [08. Diagnóstico y límites](08-diagnostico-y-limites.md)

Los miembros públicos de esta API son únicamente `.<len>`, `.<size>` y
`.<region>`. Son de solo lectura y no crean campos almacenables.

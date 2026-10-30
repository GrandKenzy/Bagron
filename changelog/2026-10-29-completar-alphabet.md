# Ampliación de `alphabet.bg`

El módulo canónico de alfabetos deja de limitarse a decimal y alfabeto mixto.
Ahora expone cadenas para:

- bases binarias, octales y hexadecimales en mayúsculas/minúsculas;
- alfabetos alfabéticos, alfanuméricos y Base36;
- Base64 y Base64 URL-safe;
- identificadores, signos, marcadores `xX` y símbolos de operadores.

Todas las constantes son `chain` públicas y no añaden coste de ejecución.

`formatting.bg` reutiliza `NumericString` y `console.bg` reutiliza
`HexadecimalUpperString`, evitando duplicar tablas de caracteres en los
módulos consumidores.

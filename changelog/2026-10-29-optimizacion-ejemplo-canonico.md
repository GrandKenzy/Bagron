# Optimización del ejemplo canónico

El ejemplo Windows se reorganiza para que cada módulo tenga una responsabilidad
concreta y para que la frontera insegura quede localizada.

- `examples/canon/` separa tipos, operaciones numéricas, consola Windows,
  serialización, reloj, constantes y ensamblador.
- `standard.bg` queda como fachada para la serialización y la impresión de
  enteros, mientras `console.bg` conserva la ABI de `kernel32`.
- Se documentan los contratos de ABI, arrays expansivos, layout LLVM y salida
  de texto sin introducir sintaxis nueva.

Comprobación principal:

```text
vnma run main.py examples/canon/_main.bg
```

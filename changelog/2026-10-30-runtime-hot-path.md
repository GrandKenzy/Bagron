# Optimización del hot path de runtime

La compilación `prod`/`high` ahora aprovecha más información que Bagron ya
conoce sin cambiar la sintaxis ni la ABI pública:

- `inline` se publica como `alwaysinline` en LLVM y las fachadas calientes de
  `console.bg` y `standard.bg` lo declaran explícitamente.
- Los helpers assembler de una sola instrucción que solo ensanchan y devuelven
  un entero se reemplazan internamente por `trunc`; la definición nativa se
  conserva para llamadas externas.
- `printb` obtiene los nibbles con desplazamiento y máscara, y su scratch de
  512 bytes se limpia con `llvm.memset` en lugar de stores individuales.
- Los `const char[N]` inicializados con literales se internan en el pool de
  rodata. Los arrays mutables y los casos dinámicos mantienen su almacenamiento
  original.
- Un `while indice < length` sobre un `buffer[]` puede reutilizar la prueba de
  rango cuando `length` es su `Len_t`, el cuerpo termina con una única
  actualización del índice y el descriptor no se reasigna ni escapa. La
  optimización solo elimina la comprobación redundante; no infiere aliasing.
- Los parámetros de arrays reciben `nonnull` y, si su extensión es fija,
  `dereferenceable(N)`. `noalias` continúa limitado a arrays `unique`; los
  arrays ordinarios, `buffer` y `chain` no reciben exclusividad inventada.
- El pipeline escalar LLVM añade simplificación/rotación/reducción de loops,
  GVN, eliminación de stores, unrolling y DCE agresivo después de la expansión
  explícita de `inline`.

`dev` conserva la representación más visible: no usa la especialización
`trunc`, mantiene los slots de iteradores y reserva local para los arrays
constantes. Las garantías de límites, `volatile`, `break`, `continue`, el paso
no nulo y `Region_t` no cambian.

El benchmark de referencia ejecutado en esta revisión terminó con:

```text
benchmark_redirect: control 17 ticks, buffer 319--320 ticks, file 144646--582099 ticks
benchmark: write_chars 164 us/op, printb_raw 183 us/op,
           printb_hex 139 us/op, write_text 552 us/op
```

Son cifras de una ejecución local en Windows y sirven para comparar futuras
revisiones, no como umbrales absolutos.

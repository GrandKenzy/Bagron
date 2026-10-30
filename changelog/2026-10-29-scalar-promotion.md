# Promoción escalar junto a buffers grandes

Los perfiles `prod` y `high` ya no omiten toda la optimización de una función
solo porque contenga un array grande. El buffer conserva una `alloca`
direccionable y su inicialización cero se emite como `memset`; SROA puede
promover los escalares cercanos sin convertir el agregado en miles de stores.

`Len_t` y `Size_t` son metadatos inmutables suministrados por el compilador.
Ahora se representan directamente con los argumentos SSA del ABI, incluyendo
sus reenvíos, en lugar de crear slots temporales.

La primera medición de `benchmark_redirect.bg` pasó de aproximadamente 827 a
378 ticks en la ruta de buffer; las repeticiones posteriores oscilaron entre
580 y 729 ticks por la variación normal del equipo. El IR confirma que
conserva `[32768 x i8]`, usa `llvm.memset` y elimina los `alloca` de los
metadatos.

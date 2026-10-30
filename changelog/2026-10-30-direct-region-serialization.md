# Serialización directa por regiones

La fase básica del plan de optimizaciones agresivas elimina la memoria
intermedia del benchmark de redirección:

```text
build_record(record, value) -> record -> output
build_record(output, position, value)
```

`examples/canon/formatting.bg` expone inline `serialize_int64_at` y su núcleo
privado. `examples/canon/benchmark_redirect.bg` conserva `unique`, `Region_t`,
`Len_t` y `Size_t`, pero escribe directamente en el buffer final; el consumo
posterior usa un préstamo `unique` para expresar su exclusividad. C y Rust se
ajustaron al mismo algoritmo.

La salida de las tres variantes conserva registros de 16 000 bytes. En una
ejecución local, la mediana del caso de buffer fue aproximadamente 320 ticks
en Bagron `prod`, 279 en C `-O2` y 314 en Rust `-O3`. Las mediciones de archivo
siguen siendo variables por `WriteFile` y no constituyen un umbral.

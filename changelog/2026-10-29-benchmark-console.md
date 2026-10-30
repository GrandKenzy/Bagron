# Benchmark de consola y `printint`

Se añade `examples/canon/benchmark.bg`, un benchmark ejecutable escrito
completamente en Bagron. Usa `time_ticks` y `time_us` para medir 1000 llamadas
a `write_chars`, `printb` crudo, `printb` hexadecimal y `write_text`.

`standard.bg` incorpora `printint(int64)`, y `formatting.bg` añade la
serialización signed de 64 bits. La API histórica `print_int(int32)` se
mantiene y escala de forma segura hacia `printint`.

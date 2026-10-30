# Benchmark de consola y `printint`

Se añade `examples/canon/benchmark.bg`, un benchmark ejecutable escrito
completamente en Bagron. Usa `time_ticks` y `time_us`, descarta cinco rondas
de calentamiento y promedia diez rondas medidas de 1000 llamadas. También
resta el coste de un bucle vacío y publica mínimo, promedio y coste entero
aproximado por llamada.

`standard.bg` incorpora `printint(int64)`, y `formatting.bg` añade la
serialización signed de 64 bits. La API histórica `print_int(int32)` se
mantiene y escala de forma segura hacia `printint`.

## Línea base conservada

La medición anterior fue una única ronda directa de 1000 llamadas, antes de
agrupar hexadecimal y reutilizar el handle de `GetStdHandle`:

| Operación | Tiempo anterior (us) |
| --- | ---: |
| `write_chars` | 67354 |
| `printb` crudo | 70689 |
| `printb` hexadecimal | 25236 |
| `write_text` | 32921 |

La primera medición estable posterior a la optimización fue directa sobre la
consola Windows, con cinco calentamientos, diez muestras y 1000 iteraciones:

| Operación | Mínimo (us) | Promedio (us) | Aproximado por llamada (us) |
| --- | ---: | ---: | ---: |
| `write_chars` | 14415 | 68820 | 68 |
| `printb` crudo | 10900 | 53728 | 53 |
| `printb` hexadecimal | 7445 | 15957 | 15 |
| `write_text` | 1799 | 19307 | 19 |

El bucle vacío promedió `2 us`. La comparación es orientativa: la cifra
anterior no tenía calentamiento ni promedio estadístico, y la salida de
consola Windows depende del terminal y de la redirección. La mejora más
consistente aparece en hexadecimal y `write_text`; no se impone un umbral
absoluto dependiente del hardware.

La frontera de `console.bg` ahora centraliza la validación y la llamada a
`WriteFile`, reutiliza el handle estándar y emite hexadecimal en bloques de
512 caracteres. Se mantienen las firmas públicas y `HexadecimalUpperString`.

## Referencia C

Se añade `examples/canon/benchmark.c` con la misma carga del benchmark Bagron.
Se compiló sin warnings con clang 21.1.0 en `-O0` y `-O2`. En una ejecución
canalizada comparable, `-O0` produjo aproximadamente 1673 us para
`write_chars`, 2140 us para `printb` crudo, 1950 us para hexadecimal y 3070 us
para `write_text`, frente a aproximadamente 1952, 1946, 2048 y 1879 us de la
ejecución Bagron canalizada. Una ejecución aislada de `-O2` mostró un valor
atípico de 10874 us en `printb` hexadecimal, confirmando que el destino de salida y
la planificación del proceso dominan estas muestras pequeñas.

Estos números sirven como referencia de protocolo y no como umbral fijo:
`benchmark.c` usa llamadas Win32 directas y no reproduce la semántica completa
de validación de los módulos Bagron.

# Benchmark de redirección con `unique`

Se registró primero la línea base de
`examples/canon/benchmark_redirect.bg` sin `unique`:

```text
empty_loop_avg_us=2
buffer min_us=131 avg_us=132 per_call_us=0
file min_us=12974 avg_us=33988 per_call_us=33
```

Después, la firma de `build_record` cambió únicamente en el parámetro de
salida y su metadata:

```diff
- output: char[64]
+ output: unique char[64]
  output_length: Len_t
  output_size: Size_t
+ output_region: Region_t
```

La llamada no cambia: `build_record(record, value)`. El IR resultante contiene
`[64 x i8]* noalias` y no añade `Region_t` como argumento runtime.

Para reducir el efecto de la variación de Windows se hicieron diez corridas por
variante con el mismo ejecutable, 5 calentamientos, 10 muestras internas y
1000 iteraciones por muestra:

| Variante | buffer: mediana / media (µs) | archivo: mediana / media (µs) |
| --- | ---: | ---: |
| base | 193.5 / 205.8 | 41131.5 / 40929.9 |
| `unique` | 195.5 / 216.8 | 38785 / 41392.5 |

La diferencia no es concluyente: el buffer quedó prácticamente igual y el
archivo mostró una mediana algo menor, pero una media ligeramente mayor. El
costo dominante sigue siendo `WriteFile` y la resolución entera de
`time.bg`; `unique` habilita la promesa LLVM, pero no reduce por sí solo las
llamadas de sistema ni garantiza una mejora en `-O0`.

Como referencia adicional, una corrida de C produjo:

```text
C -O0: buffer avg_us=239, file avg_us=33300
C -O2: buffer avg_us=10,  file avg_us=30824
```

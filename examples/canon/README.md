# Ejemplo canonico

`_main.bg` coordina módulos pequeños que actualmente se validan y se compilan
en un ejecutable nativo:

- globales constantes, decimales, enteros de ancho fijo, arrays, `char`, `byte`,
  `chain` estatico y punteros nulos;
- `enum`, `struct`, `mold` y `flags` con layout LLVM nominal y acceso a
  miembros locales;
- `mold` como una unión real: sus vistas comparten el mismo almacenamiento;
- `flags Nombre uint8` como campos de bits dentro de un entero explícito, con
  orden LSB por defecto y `@order_msb` cuando se requiere;
- `@packed`, `@align(N)` y `volatile` en agregados, incluyendo accesos
  volátiles y alineación explícita en el IR;
- variables locales enteras y agregadas con inicialización determinista,
  lectura y asignación compuesta;
- direcciones explícitas con `$`, desreferenciación parentizada y acceso a
  elementos de arrays locales;
- una función `@assembler` que devuelve estado mediante `EAX` y genera un
  archivo `.asm` y un objeto nativo;
- una función `sumar` y una comprobación de agregados emitidas en LLVM y
  llamadas desde `main`;
- `for` numéricos con `ran` y recorrido de arrays con `for i: int32 in values:`;
- `func main() int32` como entrypoint LLVM y código de salida.

Responsabilidades de los módulos:

- `model.bg`: enum, estructuras, mold, flags y comprobaciones de layout;
- `math.bg`: operaciones numericas y recorridos de arrays;
- `console.bg`: ABI de `kernel32`, wrappers `inline` y escritura agrupada de
  buffers; `printb` convierte nibbles con operaciones de bits;
- `formatting.bg`: serializacion de enteros sin asignacion dinamica;
- `standard.bg`: fachada publica para utilidades numericas;
- `time.bg` y `alphabet.bg`: reloj y constantes independientes;
- `assembly.bg`: frontera minima de ensamblador;
- `benchmark.bg`: benchmark puro en Bagron para medir las escrituras de consola
  y el forwarding de `chain` como rodata;
- `_main.bg`: target, datos globales y orquestacion.

Ejecutar desde la raíz del repositorio:

```text
vnma run main.py examples/canon/_main.bg
```

El ejecutable y el LLVM IR se generan en `examples/canon/build/`.

Benchmark de consola:

```text
vnma run main.py examples/canon/benchmark.bg
```

Mide `write_chars`, `printb` en modo crudo y hexadecimal, `write_text` y un
forwarding sin I/O (`chain_forward`) con 1000 iteraciones cada uno. Ejecuta 5
rondas de calentamiento y 10 rondas medidas, resta el coste de un bucle vacío
y muestra mínimo, mediana, promedio y coste aproximado por llamada. La
ordenación de muestras ocurre fuera de la ventana medida. Los tiempos se
imprimen en microsegundos mediante `time.bg` y `printint(int64)`.

Referencia nativa en C:

```text
clang -std=c11 -O0 examples/canon/benchmark.c -o examples/canon/build/benchmark_c_O0.exe
clang -std=c11 -O2 examples/canon/benchmark.c -o examples/canon/build/benchmark_c_O2.exe
```

`benchmark.c` conserva el mismo número de rondas y llamadas, y escribe sus
métricas en `stderr` para separar la salida de prueba de los resultados.

Benchmark de redirección a memoria y archivo:

```text
vnma run main.py examples/canon/benchmark_redirect.bg
clang -std=c11 -O0 examples/canon/benchmark_redirect.c -o examples/canon/build/benchmark_redirect_c_O0.exe
clang -std=c11 -O2 examples/canon/benchmark_redirect.c -o examples/canon/build/benchmark_redirect_c_O2.exe
```

Esta variante construye registros `value=<int64>` con `char[]` y los serializa
directamente en la región destino antes de escribirlos con `WriteFile`.
`build_record` recibe `unique char[]`, `Len_t`, `Size_t` y `Region_t`; la región
se comprueba semánticamente y el parámetro oculto no cruza la ABI runtime.
Cada iteración cambia el entero y el recorrido del buffer se realiza fuera de
la ventana medida, por lo que la serialización permanece observable sin una
segunda copia temporal. `serialize_int64_at` y su núcleo interno están
marcados `inline` para exponer esta ruta al optimizador.

La ruta de lectura usa también un préstamo `unique` durante el consumo posterior
a la medición. Esto no convierte un array ordinario en `noalias`: solo conserva
la garantía explícita de que no hay alias durante ese recorrido.

El archivo canónico usa `clause Optimizations 'prod'`. Para comparar los
perfiles, cambia esa cláusula a `dev` o `high`, recompila y ejecuta de nuevo.
Cada variante informa mínimo, mediana y ticks por llamada para el control, el
buffer y el archivo; el control se muestra por separado y no se resta. Ejecuta
los dos binarios C después de compilarlos para completar la comparación.

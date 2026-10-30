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
- `console.bg`: ABI de `kernel32` y escritura de buffers;
- `formatting.bg`: serializacion de enteros sin asignacion dinamica;
- `standard.bg`: fachada publica para utilidades numericas;
- `time.bg` y `alphabet.bg`: reloj y constantes independientes;
- `assembly.bg`: frontera minima de ensamblador;
- `benchmark.bg`: benchmark puro en Bagron para medir las escrituras de consola;
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

Mide `write_chars`, `printb` en modo crudo y hexadecimal, y `write_text` con
1000 iteraciones cada uno. Ejecuta 5 rondas de calentamiento y 10 rondas
medidas, resta el coste de un bucle vacío y muestra mínimo, promedio y coste
aproximado por llamada. Los tiempos se imprimen en microsegundos mediante
`time.bg` y `printint(int64)`.

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

Esta variante construye registros `value=<int64>` con `chain` y `char[]`,
primero acumulándolos en un buffer y después escribiéndolos con `WriteFile`.
En la variante actual, `build_record` usa `unique char[64]` y `Region_t`; el
llamador sigue escribiendo solo `build_record(record, value)` y el IR conserva
la firma runtime sin el parámetro de región.

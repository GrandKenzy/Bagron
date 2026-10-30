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
